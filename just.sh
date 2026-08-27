#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
image="${ZMK_WORKSPACE_CONTAINER_IMAGE:-zmk-workspace-dev:latest}"
workspace="/zmk-workspace"
dockerfile="$repo_dir/.devcontainer/Dockerfile"

storage_value="${ZMK_WORK_ROOT:-.zmk-workspace}"
case "$storage_value" in
    "$workspace")
        storage_rel="."
        ;;
    "$workspace"/*)
        storage_rel="${storage_value#"$workspace"/}"
        ;;
    "$repo_dir")
        storage_rel="."
        ;;
    "$repo_dir"/*)
        storage_rel="${storage_value#"$repo_dir"/}"
        ;;
    /*)
        echo "ZMK_WORK_ROOT must be inside $repo_dir so Docker can access it: $storage_value" >&2
        exit 2
        ;;
    *)
        storage_rel="${storage_value#./}"
        ;;
esac

storage_dir="$(realpath -m "$repo_dir/$storage_rel")"
container_storage_dir="$(realpath -m "$workspace/$storage_rel")"
active_profile_file="$storage_dir/active-profile"

requested_profile="${ZMK_WORK_PROFILE:-}"
if [[ "${1:-}" == "--profile" || "${1:-}" == "-p" ]]; then
    requested_profile="${2:-}"
    if [[ -z "$requested_profile" ]]; then
        echo "Usage: ./just.sh --profile <name> <command> [args...]" >&2
        exit 2
    fi
    shift 2
fi

if [[ -n "$requested_profile" ]]; then
    profile="$requested_profile"
elif [[ -f "$active_profile_file" ]]; then
    profile="$(<"$active_profile_file")"
else
    profile="default"
fi

validate_profile() {
    local value="$1"
    if [[ ! "$value" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
        echo "Invalid profile '$value'. Use letters, numbers, dot, underscore, or hyphen." >&2
        return 2
    fi
}
validate_profile "$profile"

profile_dir="$storage_dir/profiles/$profile"
profile_metadata_dir="$profile_dir/metadata"
config_name_overridden=false
config_branch_overridden=false
[[ -n "${ZMK_CONFIG_NAME:-}" ]] && config_name_overridden=true
[[ -n "${ZMK_CONFIG_BRANCH:-}" ]] && config_branch_overridden=true

sanitize_firmware_component() {
    local value="$1"
    value="$(printf '%s' "$value" | sed 's/[[:space:]":<>|*?\\\/]/-/g; s/^-*//; s/-*$//')"
    [[ -n "$value" ]] || value="$profile"
    printf '%s\n' "$value"
}

load_profile_metadata() {
    local value

    if [[ -z "${ZMK_CONFIG_NAME:-}" && -f "$profile_metadata_dir/config-name" ]]; then
        value="$(<"$profile_metadata_dir/config-name")"
        ZMK_CONFIG_NAME="$(sanitize_firmware_component "$value")"
        export ZMK_CONFIG_NAME
    fi
    if [[ -z "${ZMK_CONFIG_BRANCH:-}" && -f "$profile_metadata_dir/config-branch" ]]; then
        value="$(<"$profile_metadata_dir/config-branch")"
        ZMK_CONFIG_BRANCH="$(sanitize_firmware_component "$value")"
        export ZMK_CONFIG_BRANCH
    fi
}

config_root_from_west() {
    local west_config="$host_west_workspace/.west/config"
    local path file west_yml_path

    [[ -f "$west_config" ]] || return 1
    path="$(awk -F ' *= *' '/^ *path/ {print $2}' "$west_config")"
    file="$(awk -F ' *= *' '/^ *file/ {print $2}' "$west_config")"
    west_yml_path="$host_west_workspace/${path:-.}/${file}"
    realpath -m "$(dirname "$west_yml_path")/.."
}

save_profile_metadata() {
    local config_root git_root remote_url config_name config_branch

    config_root="$(config_root_from_west)" || return 1
    git_root="$(git -C "$config_root" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -n "$git_root" && "$(realpath -m "$git_root")" == "$(realpath -m "$config_root")" ]]; then
        remote_url="$(git -C "$config_root" remote get-url origin 2>/dev/null || true)"
        if [[ -n "$remote_url" ]]; then
            config_name="$(basename "${remote_url%/}")"
            config_name="${config_name%.git}"
        else
            config_name="$(basename "$config_root")"
        fi
        config_branch="$(git -C "$config_root" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
        [[ -n "$config_branch" ]] || config_branch="$profile"
    else
        config_name="$profile"
        config_branch="$profile"
    fi

    config_name="$(sanitize_firmware_component "$config_name")"
    config_branch="$(sanitize_firmware_component "$config_branch")"
    mkdir -p "$profile_metadata_dir"
    printf '%s\n' "$config_name" > "$profile_metadata_dir/config-name"
    printf '%s\n' "$config_branch" > "$profile_metadata_dir/config-branch"
    printf '%s\n' "$config_root" > "$profile_metadata_dir/config-root"
}

print_help() {
    cat <<'EOF'
Workspace storage commands:
  ./just.sh profile [name]              Show or select the persistent profile
  ./just.sh profiles                    List stored profiles
  ./just.sh --profile <name> <command>  Use a profile for one command
  ./just.sh paths                       Show directories used by the profile
  ./just.sh organize --dry-run          Preview legacy directory archival
  ./just.sh organize --apply            Archive legacy directories without deleting them

Build commands:
EOF
    just --list --unsorted
}

if [[ -z "${1:-}" || "${1:-}" == "help" || "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_help
    exit 0
fi

container_profile_dir="$container_storage_dir/profiles/$profile"
ccache_dir="$storage_dir/cache/ccache"

workspace_path_to_host() {
    local value="$1"
    case "$value" in
        "$workspace") printf '%s\n' "$repo_dir" ;;
        "$workspace"/*) printf '%s/%s\n' "$repo_dir" "${value#"$workspace"/}" ;;
        /*) printf '%s\n' "$value" ;;
        *) printf '%s/%s\n' "$repo_dir" "${value#./}" ;;
    esac
}

container_path() {
    local value="$1"
    case "$value" in
        "$repo_dir") printf '%s\n' "$workspace" ;;
        "$repo_dir"/*) printf '%s/%s\n' "$workspace" "${value#"$repo_dir"/}" ;;
        /*) printf '%s\n' "$value" ;;
        *) printf '%s/%s\n' "$workspace" "${value#./}" ;;
    esac
}

export ZMK_WORK_ROOT="$container_storage_dir"
export ZMK_WORK_PROFILE="$profile"
ZMK_BUILD_ROOT="$(container_path "${ZMK_BUILD_ROOT:-$container_profile_dir/build}")"
ZMK_WEST_WORKSPACE="$(container_path "${ZMK_WEST_WORKSPACE:-$container_profile_dir/west}")"
ZMK_LOG_ROOT="$(container_path "${ZMK_LOG_ROOT:-$container_profile_dir/logs}")"
export ZMK_BUILD_ROOT ZMK_WEST_WORKSPACE ZMK_LOG_ROOT

host_build_root="$(workspace_path_to_host "$ZMK_BUILD_ROOT")"
host_west_workspace="$(workspace_path_to_host "$ZMK_WEST_WORKSPACE")"
host_log_root="$(workspace_path_to_host "$ZMK_LOG_ROOT")"

load_profile_metadata

if [[ "${1:-}" == "profile" ]]; then
    if [[ -n "${2:-}" ]]; then
        validate_profile "$2"
        mkdir -p "$storage_dir/profiles/$2"
        printf '%s\n' "$2" > "$active_profile_file"
        echo "Active profile: $2"
        echo "Run './just.sh paths' to inspect its directories."
    else
        echo "$profile"
    fi
    exit 0
fi

if [[ "${1:-}" == "profiles" ]]; then
    printf 'Active profile: %s\n\n' "$profile"
    echo "Profiles:"
    if [[ -d "$storage_dir/profiles" ]]; then
        while IFS= read -r name; do
            marker=" "
            [[ "$name" == "$profile" ]] && marker="*"
            printf ' %s %s\n' "$marker" "$name"
        done < <(find "$storage_dir/profiles" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
    else
        echo "  (none yet)"
    fi
    exit 0
fi

if [[ "${1:-}" == "organize" ]]; then
    mode="${2:---dry-run}"
    if [[ "$mode" != "--dry-run" && "$mode" != "--apply" ]]; then
        echo "Usage: ./just.sh organize [--dry-run|--apply]" >&2
        exit 2
    fi

    mapfile -d '' legacy_paths < <(
        find "$repo_dir" -mindepth 1 -maxdepth 1 -type d \
            ! -path "$storage_dir" \
            \( -name '.build' -o -name '.build-*' -o \
               -name '.west-workspace' -o -name '.west-workspace-*' -o \
               -name '.tmp' -o -name '.tmp-*' -o \
               -name 'logs' \) -print0 | sort -z
    )

    legacy_cache="$repo_dir/.cache"
    legacy_ccache="$legacy_cache/ccache"
    migrate_ccache=false
    if [[ -d "$legacy_ccache" && ! -e "$ccache_dir" ]]; then
        migrate_ccache=true
    fi
    cache_has_remaining=false
    if [[ -d "$legacy_cache" ]]; then
        if [[ "$migrate_ccache" != "true" ]] || \
            find "$legacy_cache" -mindepth 1 -maxdepth 1 ! -name ccache -print -quit | grep -q .; then
            cache_has_remaining=true
        fi
    fi

    if ((${#legacy_paths[@]} == 0)) && [[ ! -d "$legacy_cache" ]]; then
        echo "No legacy workspace directories found."
        exit 0
    fi

    archive_id="$(date +%Y%m%d-%H%M%S)"
    archive_dir="$storage_dir/archive/$archive_id"
    echo "Legacy directories will be moved to: $archive_dir"
    if [[ "$migrate_ccache" == "true" ]]; then
        printf '  %s -> %s (shared cache)\n' "$legacy_ccache" "$ccache_dir"
    fi
    if [[ "$cache_has_remaining" == "true" ]]; then
        printf '  %s (remaining files) -> %s/.cache\n' "$legacy_cache" "$archive_dir"
    fi
    for path in "${legacy_paths[@]}"; do
        printf '  %s -> %s/%s\n' "$path" "$archive_dir" "$(basename "$path")"
    done

    if [[ "$mode" == "--dry-run" ]]; then
        echo
        echo "Dry run only. Use './just.sh organize --apply' to move them without deleting data."
        exit 0
    fi

    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        running_containers="$(docker ps --filter "ancestor=$image" --format '{{.ID}}' 2>/dev/null || true)"
        if [[ -n "$running_containers" ]]; then
            echo "A ZMK build container is running. Stop it before organizing directories." >&2
            exit 1
        fi
    fi

    mkdir -p "$archive_dir"
    if [[ "$migrate_ccache" == "true" ]]; then
        mkdir -p "$(dirname "$ccache_dir")"
        mv -- "$legacy_ccache" "$ccache_dir"
    fi
    if [[ -d "$legacy_cache" ]]; then
        if find "$legacy_cache" -mindepth 1 -print -quit | grep -q .; then
            mv -- "$legacy_cache" "$archive_dir/"
        else
            rmdir "$legacy_cache"
        fi
    fi
    for path in "${legacy_paths[@]}"; do
        mv -- "$path" "$archive_dir/"
    done
    cat > "$archive_dir/README.txt" <<EOF
These directories were archived by ./just.sh organize on $(date --iso-8601=seconds).
They were not deleted. Old CMake build trees contain absolute paths and should not
be moved back into active use; initialize a profile and rebuild instead.
EOF
    echo "Organization complete. Select a profile, run init, then build:"
    echo "  ./just.sh profile default"
    echo "  ./just.sh init <config-path>"
    exit 0
fi

firmware_dir() {
    local west_top west_config path file west_yml_path config_root git_root remote_url config_name config_branch

    config_name="${ZMK_CONFIG_NAME:-}"
    config_branch="${ZMK_CONFIG_BRANCH:-}"

    if [[ -n "$config_name" && -n "$config_branch" ]]; then
        config_name="$(sanitize_firmware_component "$config_name")"
        config_branch="$(sanitize_firmware_component "$config_branch")"
        printf '%s\n' "$repo_dir/firmware/$config_name/$config_branch"
        return
    elif [[ -f "$host_west_workspace/.west/config" ]]; then
        west_top="$host_west_workspace"
        west_config="$west_top/.west/config"
    elif [[ -f "$repo_dir/.west/config" ]]; then
        west_top="$repo_dir"
        west_config="$repo_dir/.west/config"
    else
        printf '%s\n' "$repo_dir/firmware/$profile/$profile"
        return
    fi

    path="$(awk -F ' *= *' '/^ *path/ {print $2}' "$west_config")"
    file="$(awk -F ' *= *' '/^ *file/ {print $2}' "$west_config")"
    west_yml_path="$west_top/${path:-.}/${file}"
    config_root="$(dirname "$west_yml_path")/.."
    config_root="$(realpath -m "$config_root")"
    git_root="$(git -C "$config_root" rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -n "$git_root" && "$(realpath -m "$git_root")" == "$config_root" ]]; then
        if [[ -z "$config_name" ]]; then
            remote_url="$(git -C "$config_root" remote get-url origin 2>/dev/null || true)"
            config_name="$(basename "${remote_url:-$config_root}")"
            config_name="${config_name%.git}"
        fi
        if [[ -z "$config_branch" ]]; then
            config_branch="$(git -C "$config_root" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
        fi
    else
        config_name="${config_name:-$profile}"
        config_branch="${config_branch:-$profile}"
    fi
    config_name="$(sanitize_firmware_component "${config_name:-$profile}")"
    config_branch="$(sanitize_firmware_component "${config_branch:-$profile}")"
    printf '%s\n' "$repo_dir/firmware/$config_name/$config_branch"
}

if [[ "${1:-}" == "paths" ]]; then
    cat <<EOF
Profile:   $profile
Storage:   $storage_dir
Build:     $host_build_root
West:      $host_west_workspace
Logs:      $host_log_root
ccache:    $ccache_dir
Metadata:  $profile_metadata_dir
Firmware:  $(firmware_dir)
EOF
    exit 0
fi

if [[ "${1:-}" == "flash" ]]; then
    shift
    expr="${1:-}"
    if [[ -z "$expr" ]]; then
        echo "Usage: ./just.sh flash <target> [-r] [west build args...]" >&2
        exit 2
    fi
    shift

    rebuild=false
    build_args=()
    for arg in "$@"; do
        if [[ "$arg" == "-r" ]]; then
            rebuild=true
        else
            build_args+=("$arg")
        fi
    done

    if [[ "$rebuild" == "true" ]]; then
        echo "Rebuilding before flashing..."
        "$repo_dir/just.sh" build "$expr" "${build_args[@]}"
    fi

    target="$("$repo_dir/just.sh" _parse_targets "$expr" | head -n 1)"
    if [[ -z "$target" ]]; then
        echo "No matching targets found for expression '$expr'. Aborting..." >&2
        exit 1
    fi

    IFS=, read -r board shield snippet artifact <<< "$target"
    artifact_name="${artifact:-${shield:+${shield// /+}-}${board}}"
    artifact_fs="${artifact_name//\//-}"
    uf2_path="$(firmware_dir)/$artifact_fs.uf2"

    if [[ ! -f "$uf2_path" ]]; then
        echo "Firmware file '$uf2_path' not found. Please build it first with './just.sh build \"$expr\"'." >&2
        exit 1
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Flashing '$uf2_path'..."
        exec "$repo_dir/flash.sh" "$uf2_path"
    elif grep -q -i "Microsoft" /proc/version; then
        echo "Flashing '$uf2_path'..."
        exec powershell.exe -ExecutionPolicy Bypass -File "$repo_dir/flash.ps1" -Uf2File "$(wslpath -w "$uf2_path")"
    else
        echo "Flashing '$uf2_path' is not supported on this platform." >&2
        exit 1
    fi
fi

if [[ "${1:-}" == "flash-log" ]]; then
    shift
    exec "$repo_dir/tools/zmk-flash-log.sh" "$@"
fi

if [[ "${1:-}" == "diagnose-ports" ]]; then
    shift
    exec "$repo_dir/tools/zmk-flash-log.sh" --diagnose "$@"
fi

dockerfile_hash="$(sha256sum "$dockerfile" | awk '{print $1}')"
image_hash="$(docker image inspect -f '{{ index .Config.Labels "zmk-workspace.dockerfile-sha" }}' "$image" 2>/dev/null || true)"
if [[ "$image_hash" != "$dockerfile_hash" ]]; then
    docker build \
        --label "zmk-workspace.dockerfile-sha=$dockerfile_hash" \
        -t "$image" \
        -f "$dockerfile" \
        "$repo_dir"
fi

mkdir -p "$ccache_dir"

docker_tty_args=()
if [[ -t 0 && -t 1 ]]; then
    docker_tty_args=(-it)
fi

cmake_build_parallel_level="${CMAKE_BUILD_PARALLEL_LEVEL:-}"
if [[ -z "$cmake_build_parallel_level" && "$OSTYPE" == "darwin"* ]]; then
    cmake_build_parallel_level=4
fi

docker_cmake_parallel_args=()
if [[ -n "$cmake_build_parallel_level" ]]; then
    docker_cmake_parallel_args=(--env "CMAKE_BUILD_PARALLEL_LEVEL=$cmake_build_parallel_level")
fi

docker_workspace_args=()
for name in ZMK_WORK_ROOT ZMK_WORK_PROFILE ZMK_BUILD_ROOT ZMK_WEST_WORKSPACE ZMK_LOG_ROOT ZMK_CONFIG_ROOT ZMK_CONFIG_NAME ZMK_CONFIG_BRANCH ZMK_TARGET_JOBS; do
    if [[ -n "${!name:-}" ]]; then
        docker_workspace_args+=(--env "$name=${!name}")
    fi
done

container_west_workspace="${ZMK_WEST_WORKSPACE:-$workspace/.west-workspace}"
if [[ "$container_west_workspace" != /* ]]; then
    container_west_workspace="$workspace/$container_west_workspace"
fi

command_name="${1:-}"
if docker run --rm \
    "${docker_tty_args[@]}" \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --env IN_ZMK_CONTAINER=1 \
    --env TERM="${TERM:-xterm-256color}" \
    --env CCACHE_DIR="$container_storage_dir/cache/ccache" \
    --env CCACHE_MAXSIZE="${ZMK_WORKSPACE_CCACHE_MAXSIZE:-5G}" \
    --env CCACHE_COMPILERCHECK=content \
    --env CCACHE_IGNOREOPTIONS="${ZMK_WORKSPACE_CCACHE_IGNOREOPTIONS:---specs=picolibc.specs}" \
    --env WORKSPACE_DIR="$workspace" \
    --env ZMK_BUILD_DIR="$ZMK_BUILD_ROOT" \
    --env ZMK_SRC_DIR="$container_west_workspace/zmk/app" \
    --env ZEPHYR_BASE="$container_west_workspace/zephyr" \
    "${docker_cmake_parallel_args[@]}" \
    "${docker_workspace_args[@]}" \
    --volume "$repo_dir:$workspace" \
    --workdir "$workspace" \
    "$image" \
    bash -lc 'exec "$@"' _ just "$@"; then
    if [[ "$command_name" == "init" ]]; then
        save_profile_metadata
        if [[ "$config_name_overridden" != "true" ]]; then
            unset ZMK_CONFIG_NAME
        fi
        if [[ "$config_branch_overridden" != "true" ]]; then
            unset ZMK_CONFIG_BRANCH
        fi
        load_profile_metadata
        echo "Profile metadata: $profile_metadata_dir"
        echo "Firmware: $(firmware_dir)"
    fi
else
    exit $?
fi

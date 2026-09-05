default:
    @just --list --unsorted

work_root := absolute_path(env_var_or_default('ZMK_WORK_ROOT', '.zmk-workspace'))
work_profile := env_var_or_default('ZMK_WORK_PROFILE', 'default')
profile_root := work_root / 'profiles' / work_profile
build := absolute_path(env_var_or_default('ZMK_BUILD_ROOT', profile_root / 'build'))
west_workspace := absolute_path(env_var_or_default('ZMK_WEST_WORKSPACE', profile_root / 'west'))
log_root := absolute_path(env_var_or_default('ZMK_LOG_ROOT', profile_root / 'logs'))
zmk_config_root := absolute_path(`
  if [ -n "${ZMK_CONFIG_ROOT:-}" ]; then
    printf '%s\n' "$ZMK_CONFIG_ROOT"
    exit 0
  fi

  west_workspace="${ZMK_WEST_WORKSPACE:-${ZMK_WORK_ROOT:-.zmk-workspace}/profiles/${ZMK_WORK_PROFILE:-default}/west}"
  if [ -f "$west_workspace/.west/config" ]; then
    west_top="$west_workspace"
    west_config="$west_top/.west/config"
  elif [ -f .west/config ]; then
    west_top="."
    west_config=".west/config"
  else
    printf '.\n'
    exit 0
  fi

  path=$(awk -F ' *= *' '/^ *path/ {print $2}' "$west_config")
  file=$(awk -F ' *= *' '/^ *file/ {print $2}' "$west_config")
  west_yml_path="$west_top/${path:-.}/${file:-west.yml}"
  manifest_dir="$(dirname "$west_yml_path")"
  manifest_git_root="$(git -C "$manifest_dir" rev-parse --show-toplevel 2>/dev/null || true)"
  manifest_dir_abs="$(realpath -m "$manifest_dir")"
  manifest_git_root_abs="$(realpath -m "${manifest_git_root:-/nonexistent}")"
  if [ -n "$manifest_git_root" ] && { [ "$manifest_dir_abs" = "$manifest_git_root_abs" ] || [ "$manifest_dir_abs" = "$manifest_git_root_abs/config" ]; }; then
    printf '%s\n' "$manifest_git_root"
  elif [ "$(basename "$manifest_dir")" = config ]; then
    printf '%s/..\n' "$manifest_dir"
  else
    printf '%s\n' "$manifest_dir"
  fi
`)
zmk_config_name := `
  if [ -n "${ZMK_CONFIG_NAME:-}" ]; then
    printf '%s' "$ZMK_CONFIG_NAME" | tr '/' '-' | sed 's/[[:space:]":<>|*?\\]/-/g'
    exit 0
  fi

  if [ -n "${ZMK_CONFIG_ROOT:-}" ]; then
    config_root="$ZMK_CONFIG_ROOT"
  else
    west_workspace="${ZMK_WEST_WORKSPACE:-${ZMK_WORK_ROOT:-.zmk-workspace}/profiles/${ZMK_WORK_PROFILE:-default}/west}"
    west_config="$west_workspace/.west/config"
    if [ ! -f "$west_config" ]; then
      printf '%s\n' "${ZMK_WORK_PROFILE:-default}"
      exit 0
    fi
    path=$(awk -F ' *= *' '/^ *path/ {print $2}' "$west_config")
    file=$(awk -F ' *= *' '/^ *file/ {print $2}' "$west_config")
    manifest_dir="$(dirname "$west_workspace/${path:-.}/${file:-west.yml}")"
    manifest_git_root="$(git -C "$manifest_dir" rev-parse --show-toplevel 2>/dev/null || true)"
    manifest_dir_abs="$(realpath -m "$manifest_dir")"
    manifest_git_root_abs="$(realpath -m "${manifest_git_root:-/nonexistent}")"
    if [ -n "$manifest_git_root" ] && { [ "$manifest_dir_abs" = "$manifest_git_root_abs" ] || [ "$manifest_dir_abs" = "$manifest_git_root_abs/config" ]; }; then
      config_root="$manifest_git_root"
    elif [ "$(basename "$manifest_dir")" = config ]; then
      config_root="$manifest_dir/.."
    else
      config_root="$manifest_dir"
    fi
  fi
  config_root="$(realpath -m "$config_root")"
  git_root=$(git -C "$config_root" rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$git_root" ] && [ "$(realpath -m "$git_root")" = "$config_root" ]; then
    remote_url=$(git -C "$config_root" remote get-url origin 2>/dev/null || true)
    basename "${remote_url:-$config_root}" | sed 's/\.git$//; s/[[:space:]":<>|*?\\\/]/-/g'
  else
    printf '%s\n' "${ZMK_WORK_PROFILE:-default}"
  fi
`
zmk_config_branch := `
  if [ -n "${ZMK_CONFIG_BRANCH:-}" ]; then
    printf '%s' "$ZMK_CONFIG_BRANCH" | tr '/' '-' | sed 's/[":<>|*?\\]/-/g'
    exit 0
  fi

  if [ -n "${ZMK_CONFIG_ROOT:-}" ]; then
    config_root="$ZMK_CONFIG_ROOT"
  else
    west_workspace="${ZMK_WEST_WORKSPACE:-${ZMK_WORK_ROOT:-.zmk-workspace}/profiles/${ZMK_WORK_PROFILE:-default}/west}"
    west_config="$west_workspace/.west/config"
    if [ ! -f "$west_config" ]; then
      printf '%s\n' "${ZMK_WORK_PROFILE:-default}"
      exit 0
    fi
    path=$(awk -F ' *= *' '/^ *path/ {print $2}' "$west_config")
    file=$(awk -F ' *= *' '/^ *file/ {print $2}' "$west_config")
    manifest_dir="$(dirname "$west_workspace/${path:-.}/${file:-west.yml}")"
    manifest_git_root="$(git -C "$manifest_dir" rev-parse --show-toplevel 2>/dev/null || true)"
    manifest_dir_abs="$(realpath -m "$manifest_dir")"
    manifest_git_root_abs="$(realpath -m "${manifest_git_root:-/nonexistent}")"
    if [ -n "$manifest_git_root" ] && { [ "$manifest_dir_abs" = "$manifest_git_root_abs" ] || [ "$manifest_dir_abs" = "$manifest_git_root_abs/config" ]; }; then
      config_root="$manifest_git_root"
    elif [ "$(basename "$manifest_dir")" = config ]; then
      config_root="$manifest_dir/.."
    else
      config_root="$manifest_dir"
    fi
  fi
  config_root="$(realpath -m "$config_root")"

  git_root=$(git -C "$config_root" rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$git_root" ] && [ "$(realpath -m "$git_root")" = "$config_root" ]; then
    branch=$(git -C "$config_root" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
    [ -n "$branch" ] || branch="${ZMK_WORK_PROFILE:-default}"
  else
    branch="${ZMK_WORK_PROFILE:-default}"
  fi

  printf '%s' "$branch" | tr '/' '-' | sed 's/[":<>|*?\\]/-/g'
`
out := absolute_path('firmware') / zmk_config_name / zmk_config_branch

# run a just recipe in the build container
_container *args:
    #!/usr/bin/env bash
    set -euo pipefail
    exec "{{ justfile_directory() }}/just.sh" {{ args }}

# parse build.yaml and filter targets by expression
_parse_targets $expr:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container _parse_targets "{{ expr }}"
    fi

    python3 "{{ justfile_directory() }}/scripts/build_targets.py" \
        "{{ zmk_config_root }}/build.yaml" "{{ expr }}" --format csv

# structured target stream for internal build logic
_parse_targets_json $expr:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container _parse_targets_json "{{ expr }}"
    fi

    python3 "{{ justfile_directory() }}/scripts/build_targets.py" \
        "{{ zmk_config_root }}/build.yaml" "{{ expr }}" --format jsonl

# build firmware for single board & shield combination
_build_single $target_json *west_args:
    #!/usr/bin/env bash
    set -euo pipefail
    target_json={{ quote(target_json) }}
    target_fields_file="$(mktemp)"
    target_cmake_file="$(mktemp)"
    trap 'rm -f -- "$target_fields_file" "$target_cmake_file"' EXIT
    python3 -c 'import json, sys; d=json.loads(sys.argv[1]); open(sys.argv[2], "wb").write(b"\0".join(str(d.get(k, "")).encode() for k in ("board", "shield", "snippet", "artifact-name")) + b"\0"); open(sys.argv[3], "wb").write(b"\0".join(str(x).encode() for x in d.get("cmake-argv", [])) + (b"\0" if d.get("cmake-argv") else b""))' \
        "$target_json" "$target_fields_file" "$target_cmake_file"
    mapfile -d '' target_fields < "$target_fields_file"
    board="${target_fields[0]}"
    shield="${target_fields[1]}"
    snippet="${target_fields[2]}"
    artifact="${target_fields[3]}"
    target_cmake_args=()
    mapfile -d '' target_cmake_args < "$target_cmake_file"
    artifact="${artifact:-${shield:+${shield// /+}-}${board}}"
    echo "::zmk-build-start::${artifact}"

    # Board ids may contain '/' (e.g. xiao_ble//zmk). Slashes break cp paths and mkdir.
    artifact_fs="${artifact//\//-}"
    build_dir="{{ build / '$artifact_fs' }}"
    echo "Building firmware for $artifact..."

    signature_file="$build_dir/.zmk-workspace-config"
    west_extra_args=({{ west_args }})
    cmake_args=(
        -DZephyr_DIR="{{ west_workspace }}/zephyr/share/zephyr-package/cmake"
        -DZMK_CONFIG="{{ zmk_config_root }}/config"
    )
    if [[ -f "{{ zmk_config_root }}/zephyr/module.yml" ]]; then
        cmake_args+=(-DZMK_EXTRA_MODULES="{{ zmk_config_root }}")
    fi
    if [[ -n "$shield" ]]; then
        cmake_args+=(-DSHIELD="$shield")
    fi
    build_signature="$({
        printf 'version=2\nboard=%s\nshield=%s\nsnippet=%s\nartifact=%s\nconfig=%s\nwest=%s\n' \
            "$board" "$shield" "$snippet" "$artifact" \
            "$(realpath -m '{{ zmk_config_root }}')" "$(realpath -m '{{ west_workspace }}')"
        printf 'cmake_arg=%q\n' "${cmake_args[@]}" "${target_cmake_args[@]}"
        printf 'west_arg=%q\n' "${west_extra_args[@]}"
    })"

    # Supplying CMake arguments to `west build` forces a configure on every run.
    # That refreshes generated headers and causes a large, unnecessary rebuild.
    # Existing build trees can safely let Ninja regenerate CMake only when an
    # actual dependency changes.
    if [[ -f "$build_dir/build.ninja" && ${#west_extra_args[@]} -eq 0 ]] && \
        cmp -s <(printf '%s\n' "$build_signature") "$signature_file"; then
        cmake --build "$build_dir"
    else
        pristine_args=(-p auto)
        if [[ -f "$build_dir/build.ninja" ]] && ! cmp -s <(printf '%s\n' "$build_signature") "$signature_file"; then
            pristine_args=(-p always)
            for arg in "${west_extra_args[@]}"; do
                [[ "$arg" == -p || "$arg" == --pristine || "$arg" == -p=* || "$arg" == --pristine=* ]] && pristine_args=()
            done
        fi
        (
            cd "{{ west_workspace }}"
            west build "${pristine_args[@]}" -s zmk/app -d "$build_dir" -b "$board" \
                "${west_extra_args[@]}" ${snippet:+-S "$snippet"} -- \
                "${cmake_args[@]}" "${target_cmake_args[@]}"
        )
    fi

    if [[ -f "$build_dir/zephyr/zmk.uf2" ]]; then
        mkdir -p "{{ out }}" && cp "$build_dir/zephyr/zmk.uf2" "{{ out }}/$artifact_fs.uf2"
    else
        mkdir -p "{{ out }}" && cp "$build_dir/zephyr/zmk.bin" "{{ out }}/$artifact_fs.bin"
    fi
    printf '%s\n' "$build_signature" > "$signature_file"
    echo "::zmk-build-done::${artifact}"

# build firmware for matching targets
build expr *west_args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container build "{{ expr }}" {{ west_args }}
    fi

    targets="$(just _parse_targets_json {{ expr }})"
    [[ -z "$targets" ]] && echo "No matching targets found. Aborting..." >&2 && exit 1

    while IFS= read -r target_json; do
        [[ -z "$target_json" ]] && continue
        just _build_single "$target_json" {{ west_args }}
    done <<< "$targets"

# build matching targets with automatically tuned target/compiler parallelism
build-fast expr *west_args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container build-fast "{{ expr }}" {{ west_args }}
    fi

    cores="$(nproc)"
    memory_kib="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"

    # Keep at least two cores and about 2 GiB available per concurrent target.
    target_jobs="${ZMK_TARGET_JOBS:-$((cores / 2))}"
    memory_jobs=$((memory_kib / 1024 / 2048))
    (( target_jobs < 1 )) && target_jobs=1
    (( memory_jobs < 1 )) && memory_jobs=1
    (( target_jobs > memory_jobs )) && target_jobs="$memory_jobs"
    (( target_jobs > 4 )) && target_jobs=4

    compiler_jobs="${CMAKE_BUILD_PARALLEL_LEVEL:-$((cores / target_jobs))}"
    (( compiler_jobs < 1 )) && compiler_jobs=1
    export CMAKE_BUILD_PARALLEL_LEVEL="$compiler_jobs"

    echo "Auto-tuned parallelism: targets=$target_jobs, compilers/target=$compiler_jobs (cores=$cores)"
    exec just build-parallel "{{ expr }}" "$target_jobs" {{ west_args }}

# build firmware for matching targets in parallel
build-parallel expr jobs *west_args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container build-parallel "{{ expr }}" "{{ jobs }}" {{ west_args }}
    fi

    if ! [[ "{{ jobs }}" =~ ^[1-9][0-9]*$ ]]; then
        echo "jobs must be a positive integer. Got: {{ jobs }}" >&2
        exit 2
    fi

    targets="$(just _parse_targets_json {{ expr }})"
    [[ -z "$targets" ]] && echo "No matching targets found. Aborting..." >&2 && exit 1

    # Avoid multiplying target-level parallelism by full per-target CMake parallelism.
    export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-2}"

    run_id="$(date +%Y%m%d-%H%M%S)"
    log_dir="{{ log_root }}/build-parallel-${run_id}"
    status_dir="$log_dir/status"
    mkdir -p "$status_dir"

    total="$(printf '%s\n' "$targets" | grep -c '^{')"

    count_status() {
        find "$status_dir" -type f -name "*.$1" 2>/dev/null | wc -l | tr -d ' '
    }

    print_progress() {
        local done failed running pending
        done="$(count_status done)"
        failed="$(count_status failed)"
        running="$(count_status running)"
        pending=$((total - done - failed - running))

        if [[ -t 1 ]]; then
            printf '\033[2J\033[H'
            printf 'ZMK parallel build\n'
            printf '==================\n\n'
            printf 'Targets: %s  Done: %s  Failed: %s  Running: %s  Pending: %s\n' \
                "$total" "$done" "$failed" "$running" "$pending"
            printf 'Target jobs: {{ jobs }}  CMAKE_BUILD_PARALLEL_LEVEL: %s\n' "$CMAKE_BUILD_PARALLEL_LEVEL"
            printf 'Logs: %s\n\n' "$log_dir"
            printf 'Running:\n'
            find "$status_dir" -type f -name "*.running" -printf '  - %f\n' 2>/dev/null | sed 's/\.running$//' || true
            printf '\nCompleted:\n'
            find "$status_dir" -type f -name "*.done" -printf '  - %f\n' 2>/dev/null | sed 's/\.done$//' || true
            printf '\nFailed:\n'
            find "$status_dir" -type f -name "*.failed" -printf '  - %f\n' 2>/dev/null | sed 's/\.failed$//' || true
        else
            printf '[%s] total=%s done=%s failed=%s running=%s pending=%s logs=%s\n' \
                "$(date +%H:%M:%S)" "$total" "$done" "$failed" "$running" "$pending" "$log_dir"
        fi
    }

    echo "Building matching targets with target parallelism={{ jobs }}, CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL}"
    echo "Full logs will be written to: $log_dir"
    print_progress

    status=0
    while IFS= read -r target_json; do
        [[ -z "$target_json" ]] && continue
        mapfile -d '' target_fields < <(
            python3 -c 'import json, sys; d=json.loads(sys.argv[1]); [sys.stdout.buffer.write(str(d.get(k, "")).encode() + b"\0") for k in ("board", "shield", "snippet", "artifact-name")]' \
                "$target_json"
        )
        board="${target_fields[0]}"
        shield="${target_fields[1]}"
        snippet="${target_fields[2]}"
        artifact="${target_fields[3]}"
        artifact_name="${artifact:-${shield:+${shield// /+}-}${board}}"
        artifact_fs="${artifact_name//\//-}"
        log_file="$log_dir/${artifact_fs}.log"
        running_file="$status_dir/${artifact_fs}.running"
        done_file="$status_dir/${artifact_fs}.done"
        failed_file="$status_dir/${artifact_fs}.failed"

        (
            set -euo pipefail
            printf 'board=%s\nshield=%s\nsnippet=%s\nartifact=%s\n\n' \
                "$board" "$shield" "$snippet" "$artifact" > "$log_file"
            touch "$running_file"
            if just _build_single "$target_json" {{ west_args }} >> "$log_file" 2>&1; then
                rm -f "$running_file"
                touch "$done_file"
            else
                rc=$?
                rm -f "$running_file"
                printf '%s\n' "$rc" > "$failed_file"
                exit "$rc"
            fi
        ) &

        while (( $(jobs -pr | wc -l) >= {{ jobs }} )); do
            wait -n || status=1
            print_progress
        done
    done <<< "$targets"

    while (( $(jobs -pr | wc -l) > 0 )); do
        wait -n || status=1
        print_progress
    done

    print_progress

    if (( status != 0 )); then
        echo
        echo "One or more targets failed. Showing the last 80 log lines for each failed target:"
        while IFS= read -r failed_marker; do
            artifact_fs="$(basename "$failed_marker" .failed)"
            echo
            echo "---- $artifact_fs ----"
            tail -80 "$log_dir/${artifact_fs}.log" || true
        done < <(find "$status_dir" -type f -name "*.failed" | sort)
    fi

    exit "$status"

# clear build cache and artifacts
clean:
    #!/usr/bin/env bash
    set -euo pipefail
    source "{{ justfile_directory() }}/scripts/workspace-safety.sh"
    profile={{ quote(work_profile) }}
    zmk_validate_profile "$profile"
    workspace="$(realpath -m '{{ justfile_directory() }}')"
    safe_work="$(zmk_require_symlink_free_within "{{ work_root }}" "$workspace" "work root")"
    expected_profile="$(zmk_require_safe_child "$safe_work/profiles/$profile" "$safe_work" "profile root")"
    [[ "$(realpath -ms '{{ profile_root }}')" == "$expected_profile" ]] || { echo "Refusing unexpected profile root." >&2; exit 2; }
    safe_build="$(zmk_require_safe_child "{{ build }}" "$expected_profile" "build root")"
    firmware_root="$(zmk_require_safe_child "$workspace/firmware" "$workspace" "firmware root")"
    safe_out="$(zmk_require_safe_child "{{ out }}" "$firmware_root" "firmware output")"
    rm -rf -- "$safe_build" "$safe_out"

# show ccache statistics
ccache-stats *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container ccache-stats {{ args }}
    fi

    ccache -s {{ args }}

# clear ccache data
clean-ccache:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container clean-ccache
    fi

    ccache -C

# clear all automatically generated files
clean-all:
    #!/usr/bin/env bash
    set -euo pipefail

    source "{{ justfile_directory() }}/scripts/workspace-safety.sh"
    profile={{ quote(work_profile) }}
    zmk_validate_profile "$profile"
    workspace="$(realpath -m '{{ justfile_directory() }}')"
    safe_work="$(zmk_require_symlink_free_within "{{ work_root }}" "$workspace" "work root")"
    expected_profile="$(zmk_require_safe_child "$safe_work/profiles/$profile" "$safe_work" "profile root")"
    [[ "$(realpath -ms '{{ profile_root }}')" == "$expected_profile" ]] || { echo "Refusing unexpected profile root." >&2; exit 2; }
    safe_build="$(zmk_require_safe_child "{{ build }}" "$expected_profile" "build root")"
    safe_west="$(zmk_require_safe_child "{{ west_workspace }}" "$expected_profile" "west workspace")"
    firmware_root="$(zmk_require_safe_child "$workspace/firmware" "$workspace" "firmware root")"
    safe_out="$(zmk_require_safe_child "{{ out }}" "$firmware_root" "firmware output")"

    generated=()
    if [[ -d .west ]]; then
        while IFS= read -r path; do
            case "$path" in
                "$workspace/config"| "$workspace/config/"*) ;;
                "$workspace"/*) generated+=("$(zmk_require_untracked_child "$path" "$workspace" "west project")") ;;
                *) echo "Refusing west project outside workspace: $path" >&2; exit 2 ;;
            esac
        done < <(WEST_TOPDIR="$(pwd)" west list -f '{abspath}' 2>/dev/null || true)
    fi

    fixed_generated=()
    for path in "$workspace/.west" "$workspace/zmk" "$workspace/zephyr" "$workspace/modules"; do
        fixed_generated+=("$(zmk_require_untracked_child "$path" "$workspace" "generated workspace path")")
    done

    rm -rf -- "$safe_build" "$safe_out" "$safe_west" "${fixed_generated[@]}" "${generated[@]}"

# clear nix cache
clean-nix:
    nix-collect-garbage --delete-old

# initialize west
init *config_path:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container init {{ config_path }}
    fi

    config_path="{{ config_path }}"

    # If config_path is provided as argument, use fzf to select it
    if [[ -z "$config_path" ]]; then
        # Use fzf to select config from config/ and its subdirectories
        subdirs=$(find config -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
        candidates=$(printf "config\n"; printf "%s\n" "$subdirs" | sed 's#^#config/#')

        config_path=$(echo "$candidates" | fzf \
            --prompt="Select ZMK config: " \
            --header="Choose a configuration to initialize" \
            --color="fg:#000000,bg:#ffffff,fg+:#000000,bg+:#d9d9d9,hl:#005f87,hl+:#005f87,info:#444444,prompt:#005f87,pointer:#005f87,marker:#005f87,spinner:#005f87,header:#444444" \
            --preview="ls -1a {}")

        if [[ -z "$config_path" ]]; then
            echo "No config selected. Exiting..."
            exit 0
        fi
    fi

    # Prefer the standard nested manifest when both it and a root helper
    # manifest exist. A manifest file can still be selected explicitly.
    if [[ -f "$config_path" ]]; then
        west_yml_abs="$config_path"
    elif [[ -f "$config_path/config/west.yml" ]]; then
        west_yml_abs="$config_path/config/west.yml"
    elif [[ -f "$config_path/west.yml" ]]; then
        west_yml_abs="$config_path/west.yml"
    else
        echo "No west.yml found under '$config_path'." >&2
        exit 2
    fi

    # Keep the manifest in config/, even when the west workspace is nested under
    # .zmk-workspace/profiles/<name>/west.
    mkdir -p "{{ west_workspace }}/.west"
    config_dir_abs="$(realpath config)"
    west_workspace_abs="$(realpath "{{ west_workspace }}")"
    manifest_path_rel="$(realpath --relative-to="$west_workspace_abs" "$config_dir_abs")"
    west_yml_rel="$(realpath --relative-to="$config_dir_abs" "$west_yml_abs")"

    printf '[manifest]\npath = %s\nfile = %s\n' \
        "$manifest_path_rel" "$west_yml_rel" > "{{ west_workspace }}/.west/config"

    (
        cd "{{ west_workspace }}"
        west update --fetch-opt=--filter=blob:none
        west zephyr-export
    )

# list build targets
list:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container list
    fi
    just _parse_targets all | sed 's/,*$//' | sort | column

# update west
update:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container update
    fi
    (
        cd "{{ west_workspace }}"
        west update --fetch-opt=--filter=blob:none
    )

# draw keymap SVGs with keymap-drawer
draw-keymap *names:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container draw-keymap {{ names }}
    fi

    config_root="{{ zmk_config_root }}"
    keymap_dir="$config_root/keymap-drawer"
    keymap_config="$keymap_dir/config.yaml"
    mkdir -p "$keymap_dir"

    keymap_config_args=()
    if [[ -f "$keymap_config" ]]; then
        keymap_config_args=(-c "$keymap_config")
    fi

    requested=({{ names }})
    if [[ ${#requested[@]} -eq 0 ]]; then
        mapfile -t requested < <(find "$config_root/config" -maxdepth 1 -type f -name "*.keymap" -printf "%f\n" | sed "s/\\.keymap$//" | sort)
    fi

    if [[ ${#requested[@]} -eq 0 ]]; then
        echo "No keymap files found in $config_root/config" >&2
        exit 1
    fi

    for name in "${requested[@]}"; do
        keymap_file="$config_root/config/$name.keymap"
        json_file="$config_root/config/$name.json"
        yaml_file="$keymap_dir/$name.yaml"
        svg_file="$keymap_dir/$name.svg"

        if [[ ! -f "$keymap_file" ]]; then
            echo "Keymap file not found: $keymap_file" >&2
            exit 1
        fi

        echo "Drawing keymap for $name..."
        just generate-keymap-json "$name"
        keymap "${keymap_config_args[@]}" parse -z "$keymap_file" -o "$yaml_file"

        draw_args=()
        if [[ -f "$json_file" ]]; then
            draw_args=(-j "$json_file")
        fi
        keymap "${keymap_config_args[@]}" draw "$yaml_file" "${draw_args[@]}" -o "$svg_file"
        echo "Wrote $svg_file"
    done

# generate keymap-drawer JSON from ZMK physical layouts
generate-keymap-json *names:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container generate-keymap-json {{ names }}
    fi

    config_root="{{ zmk_config_root }}"
    requested=({{ names }})
    if [[ ${#requested[@]} -eq 0 ]]; then
        mapfile -t requested < <(find "$config_root/config" -maxdepth 1 -type f -name "*.keymap" -printf "%f\n" | sed "s/\\.keymap$//" | sort)
    fi

    if [[ ${#requested[@]} -eq 0 ]]; then
        echo "No keymap files found in $config_root/config" >&2
        exit 1
    fi

    for name in "${requested[@]}"; do
        dtsi_file=$(find "$config_root" -path "$config_root/.git" -prune -o -type f \( -name "$name.dtsi" -o -name "$name.overlay" \) -print | sort | head -n 1)
        if [[ -z "$dtsi_file" ]]; then
            echo "Physical layout source not found for $name under $config_root" >&2
            exit 1
        fi

        json_file="$config_root/config/$name.json"
        layout_name="layout_$name"
        echo "Generating $json_file from $dtsi_file..."
        "{{ justfile_directory() }}/scripts/generate_keymap_drawer_json.py" \
            "$dtsi_file" "$json_file" \
            --layout "$layout_name" \
            --id "$name" \
            --name "$name"
    done

# draw keymap SVGs directly from ZMK physical layouts and .keymap files
draw-physical-layout *names:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container draw-physical-layout {{ names }}
    fi

    config_root="{{ zmk_config_root }}"
    layout_dir="$config_root/keymap-svg"
    mkdir -p "$layout_dir"

    requested=({{ names }})
    if [[ ${#requested[@]} -eq 0 ]]; then
        mapfile -t requested < <(find "$config_root/config" -maxdepth 1 -type f -name "*.keymap" -printf "%f\n" | sed "s/\\.keymap$//" | sort)
    fi

    if [[ ${#requested[@]} -eq 0 ]]; then
        echo "No keymap files found in $config_root/config" >&2
        exit 1
    fi

    for name in "${requested[@]}"; do
        keymap_file="$config_root/config/$name.keymap"
        dtsi_file=$(find "$config_root" -path "$config_root/.git" -prune -o -type f \( -name "$name.dtsi" -o -name "$name.overlay" \) -print | sort | head -n 1)
        if [[ ! -f "$keymap_file" ]]; then
            echo "Keymap file not found: $keymap_file" >&2
            exit 1
        fi
        if [[ -z "$dtsi_file" ]]; then
            echo "Physical layout source not found for $name under $config_root" >&2
            exit 1
        fi

        svg_file="$layout_dir/$name.svg"
        layout_name="layout_$name"
        echo "Drawing keymap-svg keymap for $name..."
        "{{ justfile_directory() }}/scripts/generate_physical_layout_svg.py" \
            "$dtsi_file" "$svg_file" \
            --keymap "$keymap_file" \
            --layout "$layout_name"
        echo "Wrote $svg_file"
    done

# upgrade zephyr-sdk and python dependencies
upgrade-sdk:
    nix flake update --flake .

# flash firmware for matching targets
flash expr *args:
    #!/usr/bin/env bash
    set -euo pipefail

    # Check if -r option is provided
    rebuild=false
    target_mount="${FLASH_TARGET_MOUNT:-}"
    target_drive="${FLASH_TARGET_DRIVE:-}"
    build_args=()
    set -- {{ args }}
    while (( $# > 0 )); do
        case "$1" in
            -r) rebuild=true; shift ;;
            --mount)
                (( $# >= 2 )) || { echo "--mount requires a value." >&2; exit 2; }
                target_mount="$2"; shift 2 ;;
            --drive)
                (( $# >= 2 )) || { echo "--drive requires a value." >&2; exit 2; }
                target_drive="$2"; shift 2 ;;
            *) build_args+=("$1"); shift ;;
        esac
    done

    targets_output="$(just _parse_targets_json {{ expr }})"
    targets=()
    while IFS= read -r candidate; do
        [[ -z "$candidate" ]] || targets+=("$candidate")
    done <<< "$targets_output"
    if (( ${#targets[@]} == 0 )); then
        echo "No matching targets found for expression '{{ expr }}'. Aborting..." >&2
        exit 1
    fi
    if (( ${#targets[@]} != 1 )); then
        echo "Expression '{{ expr }}' matches multiple targets; choose one of:" >&2
        for candidate in "${targets[@]}"; do
            python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print("  " + ", ".join(f"{k}={d[k]}" for k in ("artifact-name", "board", "shield", "snippet", "cmake-args") if d.get(k)))' "$candidate" >&2
        done
        exit 2
    fi
    target="${targets[0]}"

    # Rebuild only after the flash expression has proved unique.
    if [[ "$rebuild" == "true" ]]; then
        echo "Rebuilding before flashing..."
        just build "{{ expr }}" "${build_args[@]}"
    fi

    mapfile -d '' target_fields < <(
        python3 -c 'import json, sys; d=json.loads(sys.argv[1]); [sys.stdout.buffer.write(str(d.get(k, "")).encode() + b"\0") for k in ("board", "shield", "snippet", "artifact-name")]' "$target"
    )
    board="${target_fields[0]}"
    shield="${target_fields[1]}"
    snippet="${target_fields[2]}"
    artifact="${target_fields[3]}"
    # Use artifact-name if specified, otherwise construct from shield and board
    if [[ -n "$artifact" ]]; then
        artifact_name="$artifact"
    else
        artifact_name="${shield:+${shield// /+}-}${board}"
    fi
    artifact_fs="${artifact_name//\//-}"
    uf2_file="$artifact_fs.uf2"
    uf2_path="{{ out }}/$uf2_file"

    if [[ ! -f "$uf2_path" ]]; then
        echo "Firmware file '$uf2_path' not found. Please build it first with 'just build \"{{ expr }}\"'." >&2
        exit 1
    fi

    # macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        [[ -z "$target_drive" ]] || { echo "--drive is only valid on Windows/WSL." >&2; exit 2; }
        echo "Flashing '$uf2_path'..."
        if [[ -n "$target_mount" ]]; then
            ./flash.sh "$uf2_path" "$target_mount"
        else
            ./flash.sh "$uf2_path"
        fi
    # WSL
    elif grep -q -i "Microsoft" /proc/version; then
        [[ -z "$target_mount" ]] || { echo "--mount is only valid on macOS." >&2; exit 2; }
        echo "Flashing '$uf2_path'..."
        if [[ -n "$target_drive" ]]; then
            powershell.exe -ExecutionPolicy Bypass -File flash.ps1 -Uf2File "$(wslpath -w "$uf2_path")" -DriveLetter "$target_drive"
        else
            powershell.exe -ExecutionPolicy Bypass -File flash.ps1 -Uf2File "$(wslpath -w "$uf2_path")"
        fi
    # Other: Not supported
    else
        echo "Flashing '$uf2_path' is not supported on this platform." >&2
        exit 1
    fi

[no-cd]
test $testpath *FLAGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${IN_ZMK_CONTAINER:-0}" != "1" ]]; then
        exec just _container test "{{ testpath }}" {{ FLAGS }}
    fi

    testcase=$(basename "$testpath")
    build_dir="{{ build / "tests" / '$testcase' }}"
    config_dir="{{ '$(pwd)' / '$testpath' }}"
    cd {{ justfile_directory() }}

    if [[ "{{ FLAGS }}" != *"--no-build"* ]]; then
        echo "Running $testcase..."
        rm -rf "$build_dir"
        (
            cd "{{ west_workspace }}"
            west build -s zmk/app -d "$build_dir" -b native_posix_64 -- \
                -DZephyr_DIR="{{ west_workspace }}/zephyr/share/zephyr-package/cmake" \
                -DCONFIG_ASSERT=y -DZMK_CONFIG="$config_dir" \
                ${ZMK_EXTRA_MODULES:+-DZMK_EXTRA_MODULES="$(realpath ${ZMK_EXTRA_MODULES})"}
        )
    fi

    ${build_dir}/zephyr/zmk.exe | sed -e "s/.*> //" |
        tee ${build_dir}/keycode_events.full.log |
        sed -n -f ${config_dir}/events.patterns > ${build_dir}/keycode_events.log
    if [[ "{{ FLAGS }}" == *"--verbose"* ]]; then
        cat ${build_dir}/keycode_events.log
    fi

    if [[ "{{ FLAGS }}" == *"--auto-accept"* ]]; then
        cp ${build_dir}/keycode_events.log ${config_dir}/keycode_events.snapshot
    fi
    diff -auZ ${config_dir}/keycode_events.snapshot ${build_dir}/keycode_events.log

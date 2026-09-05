#!/usr/bin/env bash

# Shared path guards for commands that remove generated workspace data.
# This file is sourced by both the host wrapper and recipes in the container.

zmk_canonical_path() {
    realpath -m -- "$1"
}

zmk_lexical_path() {
    realpath -ms -- "$1"
}

zmk_reject_symlink_components() {
    local candidate_abs="$1"
    local allowed_abs="$2"
    local label="${3:-path}"
    local relative current part
    local -a parts

    if [[ -L "$allowed_abs" ]]; then
        echo "Refusing unsafe $label with symlink component: $allowed_abs" >&2
        return 2
    fi
    relative="${candidate_abs#"$allowed_abs"/}"
    current="$allowed_abs"
    IFS='/' read -r -a parts <<< "$relative"
    for part in "${parts[@]}"; do
        [[ -n "$part" ]] || continue
        current="$current/$part"
        if [[ -L "$current" ]]; then
            echo "Refusing unsafe $label with symlink component: $current" >&2
            return 2
        fi
    done
}

zmk_require_symlink_free_within() {
    local candidate="$1"
    local allowed_root="$2"
    local label="${3:-path}"
    local candidate_abs allowed_abs candidate_real allowed_real

    candidate_abs="$(zmk_lexical_path "$candidate")"
    allowed_abs="$(zmk_lexical_path "$allowed_root")"
    case "$candidate_abs" in
        "$allowed_abs"|"$allowed_abs"/*) ;;
        *)
            echo "Refusing unsafe $label outside $allowed_abs: $candidate_abs" >&2
            return 2
            ;;
    esac
    zmk_reject_symlink_components "$candidate_abs" "$allowed_abs" "$label" || return
    candidate_real="$(zmk_canonical_path "$candidate_abs")"
    allowed_real="$(zmk_canonical_path "$allowed_abs")"
    case "$candidate_real" in
        "$allowed_real"|"$allowed_real"/*) ;;
        *)
            echo "Refusing unsafe $label outside $allowed_real: $candidate_real" >&2
            return 2
            ;;
    esac
    printf '%s\n' "$candidate_abs"
}

zmk_require_within() {
    local candidate="$1"
    local allowed_root="$2"
    local label="${3:-path}"
    local candidate_abs allowed_abs

    candidate_abs="$(zmk_canonical_path "$candidate")"
    allowed_abs="$(zmk_canonical_path "$allowed_root")"
    case "$candidate_abs" in
        "$allowed_abs"|"$allowed_abs"/*) printf '%s\n' "$candidate_abs" ;;
        *)
            echo "Refusing unsafe $label outside $allowed_abs: $candidate_abs" >&2
            return 2
            ;;
    esac
}

zmk_validate_profile() {
    local value="$1"
    if [[ ! "$value" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
        echo "Invalid profile '$value'. Use letters, numbers, dot, underscore, or hyphen." >&2
        return 2
    fi
}

zmk_require_safe_child() {
    local candidate="$1"
    local allowed_root="$2"
    local label="${3:-path}"
    local candidate_abs allowed_abs

    if [[ -z "$candidate" || -z "$allowed_root" ]]; then
        echo "Refusing unsafe $label: path is empty." >&2
        return 2
    fi

    candidate_abs="$(zmk_lexical_path "$candidate")"
    allowed_abs="$(zmk_lexical_path "$allowed_root")"

    case "$candidate_abs" in
        /|"$allowed_abs")
            echo "Refusing unsafe $label: $candidate_abs" >&2
            return 2
            ;;
        "$allowed_abs"/*)
            zmk_reject_symlink_components "$candidate_abs" "$allowed_abs" "$label" || return
            local candidate_real allowed_real
            candidate_real="$(zmk_canonical_path "$candidate_abs")"
            allowed_real="$(zmk_canonical_path "$allowed_abs")"
            case "$candidate_real" in
                "$allowed_real"/*) printf '%s\n' "$candidate_abs" ;;
                *)
                    echo "Refusing unsafe $label outside $allowed_real: $candidate_real" >&2
                    return 2
                    ;;
            esac
            ;;
        *)
            echo "Refusing unsafe $label outside $allowed_abs: $candidate_abs" >&2
            return 2
            ;;
    esac
}

zmk_require_untracked_child() {
    local candidate="$1"
    local workspace_root="$2"
    local label="${3:-generated path}"
    local candidate_abs workspace_abs relative

    candidate_abs="$(zmk_require_safe_child "$candidate" "$workspace_root" "$label")" || return
    workspace_abs="$(zmk_lexical_path "$workspace_root")"
    relative="${candidate_abs#"$workspace_abs"/}"
    case "$relative" in
        config|config/*|.git|.git/*)
            echo "Refusing unsafe $label in protected workspace data: $candidate_abs" >&2
            return 2
            ;;
    esac
    local tracked
    if ! tracked="$(git -C "$workspace_abs" --literal-pathspecs ls-files -- "$relative" 2>/dev/null)"; then
        echo "Refusing unsafe $label because Git tracking state is unavailable: $candidate_abs" >&2
        return 2
    fi
    if [[ -n "$tracked" ]]; then
        echo "Refusing unsafe $label containing tracked files: $candidate_abs" >&2
        return 2
    fi
    printf '%s\n' "$candidate_abs"
}

#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

to_windows_path() {
    local path="$1"
    case "$path" in
        /mnt/[a-zA-Z]/*)
            local drive rest
            drive="${path:5:1}"
            rest="${path:7}"
            printf '%s:/%s\n' "${drive^^}" "$rest"
            ;;
        *)
            wslpath -m "$path"
            ;;
    esac
}

windows_temp_dir() {
    local candidate
    for candidate in /mnt/c/Users/*/AppData/Local/Temp; do
        [[ -d "$candidate" && -w "$candidate" ]] || continue
        case "$candidate" in
            *"/Default/"*|*"Default User"*) continue ;;
        esac
        printf '%s\n' "$candidate"
        return 0
    done

    echo "Could not find a writable Windows temp directory under /mnt/c/Users." >&2
    return 1
}

usage() {
    cat >&2 <<'USAGE'
Usage:
  tools/zmk-flash-log.sh <artifact-or-uf2> <trigger COM port> [options]
  tools/zmk-flash-log.sh --resolve <artifact-or-uf2>
  tools/zmk-flash-log.sh --diagnose [trigger COM port] [options]

Examples:
  tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --build --seconds 90
  tools/zmk-flash-log.sh firmware/zmk-config-example/main/MY_KEYBOARD_RIGHT.uf2 COM12
  tools/zmk-flash-log.sh --diagnose COM12 --log-port COM12

Options:
  --build                 Run ./just.sh build <artifact> before flashing.
  --seconds <n>           Capture serial log for n seconds. Default: 60.
  --baud <n>              Serial log baud rate. Default: 115200.
  --log-port <COM port>   Read serial logs from a different COM port.
  --drive <letter>        Restrict UF2 drive detection to a drive letter.
  --log <path>            Output log path. Default: <profile-logs>/zmk/<artifact>-timestamp.log.
  --log-dir <path>        Output log directory when --log is omitted. Default: <profile-logs>/zmk.
  --blocked-ports "..."   Refuse to use these ports. Default: ZMK_FLASH_BLOCKED_PORTS or empty.
  --bootloader-baud <n>   Baud used to trigger bootloader. Default: 1200.
  --bootloader-delay-ms <n>
                          Delay around bootloader trigger open/close. Default: 300.
  --flash-timeout <n>     Seconds to wait for UF2 drive. Default: 60.
  --post-flash-delay-ms <n>
                          Delay before opening serial log after UF2 copy. Default: 200.
  --skip-flash            Only capture log.
  --skip-log              Only flash firmware.
  --diagnose              Print Windows-side diagnostics and exit.
  --resolve               Print the exact UF2 path; do not build, flash, or open serial ports.
                          Uses just.sh profile selection (including ZMK_WORK_PROFILE).
USAGE
}

active_firmware_dir() {
    bash "$repo_dir/just.sh" firmware-dir
}

diagnose=false
resolve_only=false
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "${1:-}" == "--diagnose" ]]; then
    diagnose=true
    shift
elif [[ "${1:-}" == "--resolve" ]]; then
    resolve_only=true
    shift
fi

if [[ "$diagnose" == false && "$resolve_only" == false && $# -lt 2 ]] ||
   [[ "$resolve_only" == true && $# -lt 1 ]]; then
    usage
    exit 2
fi

target=""
port=""
if [[ "$diagnose" == "true" ]]; then
    if [[ "${1:-}" == --* ]]; then
        port=""
    else
        port="${1:-}"
        [[ $# -gt 0 ]] && shift
    fi
elif [[ "$resolve_only" == true ]]; then
    target="$1"
    shift
else
    target="$1"
    port="$2"
    shift 2
fi

do_build=false
seconds=60
baud=115200
log_port="$port"
drive=""
log_path=""
log_dir=""
skip_flash=false
skip_log=false
post_flash_delay_ms=200
bootloader_baud=1200
bootloader_delay_ms=300
flash_timeout=60

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            do_build=true
            shift
            ;;
        --seconds)
            seconds="${2:?--seconds requires a value}"
            shift 2
            ;;
        --baud)
            baud="${2:?--baud requires a value}"
            shift 2
            ;;
        --log-port)
            log_port="${2:?--log-port requires a value}"
            shift 2
            ;;
        --drive)
            drive="${2:?--drive requires a value}"
            shift 2
            ;;
        --log)
            log_path="${2:?--log requires a value}"
            shift 2
            ;;
        --log-dir)
            log_dir="${2:?--log-dir requires a value}"
            shift 2
            ;;
        --blocked-ports)
            blocked_ports="${2:?--blocked-ports requires a value}"
            shift 2
            ;;
        --bootloader-baud)
            bootloader_baud="${2:?--bootloader-baud requires a value}"
            shift 2
            ;;
        --bootloader-delay-ms)
            bootloader_delay_ms="${2:?--bootloader-delay-ms requires a value}"
            shift 2
            ;;
        --flash-timeout)
            flash_timeout="${2:?--flash-timeout requires a value}"
            shift 2
            ;;
        --post-flash-delay-ms)
            post_flash_delay_ms="${2:?--post-flash-delay-ms requires a value}"
            shift 2
            ;;
        --skip-flash)
            skip_flash=true
            shift
            ;;
        --skip-log)
            skip_log=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ "$resolve_only" == true && "$do_build" == true ]]; then
    echo "--resolve cannot be combined with --build." >&2
    exit 2
fi

normalize_com_port() {
    printf '%s\n' "${1^^}"
}

blocked_ports="${blocked_ports:-${ZMK_FLASH_BLOCKED_PORTS:-}}"
for blocked_port in $blocked_ports; do
    blocked_port="$(normalize_com_port "$blocked_port")"
    if [[ "$(normalize_com_port "$port")" == "$blocked_port" ||
          "$(normalize_com_port "$log_port")" == "$blocked_port" ]]; then
        echo "Refusing to use blocked COM port: $blocked_port" >&2
        echo "Override with --blocked-ports or ZMK_FLASH_BLOCKED_PORTS if this port is intentionally reassigned." >&2
        exit 2
    fi
done

if [[ "$diagnose" == "true" ]]; then
    artifact="diagnostic"
    uf2_path="$repo_dir/tools/zmk-flash-log.ps1"
elif [[ "$target" == *.uf2 || -f "$target" ]]; then
    uf2_path="$(realpath -m "$target")"
    artifact="$(basename "$uf2_path" .uf2)"
else
    artifact="$target"
    if [[ "$do_build" == "true" ]]; then
        "$repo_dir/just.sh" build "$artifact"
    fi
    firmware_dir="$(active_firmware_dir)"
    uf2_path="$firmware_dir/${artifact//\//-}.uf2"
fi

if [[ "$diagnose" == "false" && ! -f "$uf2_path" ]]; then
    echo "UF2 not found: $uf2_path" >&2
    echo "Build it in the selected profile, or specify an explicit UF2 path. Other branches are not searched." >&2
    exit 1
fi

if [[ "$resolve_only" == true ]]; then
    printf '%s\n' "$uf2_path"
    exit 0
fi

if [[ -z "$log_path" ]]; then
    [[ -n "$log_dir" ]] || log_dir="$(bash "$repo_dir/just.sh" log-dir)/zmk"
    mkdir -p "$log_dir"
    log_path="$log_dir/${artifact}-$(date +%Y%m%d-%H%M%S).log"
fi

host_temp="$(windows_temp_dir)"
run_temp="$host_temp/zmk-flash-log-$$"
mkdir -p "$run_temp"

cp "$repo_dir/tools/zmk-flash-log.ps1" "$run_temp/zmk-flash-log.ps1"
if [[ "$diagnose" == "false" ]]; then
    cp "$uf2_path" "$run_temp/$(basename "$uf2_path")"
fi

temp_log="$run_temp/$(basename "$log_path")"
ps_script="$(to_windows_path "$run_temp/zmk-flash-log.ps1")"
ps_uf2="$(to_windows_path "$run_temp/$(basename "$uf2_path")")"
ps_log="$(to_windows_path "$temp_log")"

args=(
    -NoProfile
    -ExecutionPolicy Bypass
    -File "$ps_script"
    -Uf2File "$ps_uf2"
    -TriggerPort "$port"
    -LogPort "$log_port"
    -LogSeconds "$seconds"
    -LogBaudRate "$baud"
    -BootloaderBaudRate "$bootloader_baud"
    -BootloaderDelayMs "$bootloader_delay_ms"
    -FlashTimeoutSeconds "$flash_timeout"
    -LogPath "$ps_log"
    -PostFlashLogDelayMs "$post_flash_delay_ms"
)

if [[ -n "$drive" ]]; then
    args+=(-DriveLetter "$drive")
fi
if [[ "$skip_flash" == "true" ]]; then
    args+=(-SkipFlash)
fi
if [[ "$skip_log" == "true" ]]; then
    args+=(-SkipLog)
fi
if [[ "$diagnose" == "true" ]]; then
    args+=(-DiagnoseOnly)
fi

powershell.exe "${args[@]}"

if [[ "$diagnose" == "false" && "$skip_log" != "true" && -f "$temp_log" ]]; then
    mkdir -p "$(dirname "$log_path")"
    cp "$temp_log" "$log_path"
    echo "Copied log to $log_path"
fi

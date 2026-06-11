# ZMK flash / log loop

This document describes the reusable firmware flashing and serial-log capture loop used by this workspace.

The goal is to make the following cycle repeatable from Codex or a terminal:

1. Build a target when needed.
2. Open and close the ZMK USB serial port at 1200 baud to enter the UF2 bootloader.
3. Copy the selected UF2 file to the UF2 drive.
4. Wait for the board to reboot.
5. Capture ZMK USB serial logs into a timestamped file.

## Tools

- `tools/zmk-flash-log.sh`
  - Reusable WSL entry point.
  - Resolves artifacts from the active `just init` config.
  - Copies the PowerShell helper and UF2 into a Windows temp directory.
  - Calls `powershell.exe` so Windows can access COM ports and UF2 drives.
- `tools/zmk-flash-log.ps1`
  - Windows-side implementation.
  - Triggers the bootloader, detects UF2 drives, copies firmware, and captures serial logs.

Keyboard-specific wrappers and local COM-port notes should live in the keyboard config repository or in ignored local notes, not in this generic workspace.

## Requirements

- The firmware must include a CDC ACM bootloader trigger, such as `zmk-feature-cdc-acm-bootloader-trigger`.
- USB serial logging must be enabled on the side connected to USB.
- The first firmware containing the bootloader trigger must be flashed manually.
- On WSL, run the helper from the WSL workspace. The helper invokes Windows PowerShell internally.

## Basic Usage

Build, flash, and capture 90 seconds of logs:

```sh
tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --build --seconds 90
```

Flash an already-built artifact:

```sh
tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --seconds 60
```

Flash a specific UF2 path:

```sh
tools/zmk-flash-log.sh firmware/zmk-config-example/main/MY_KEYBOARD_RIGHT.uf2 COM12 --seconds 60
```

Capture logs without flashing:

```sh
tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --skip-flash --seconds 120
```

Flash without capturing logs:

```sh
tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --skip-log
```

Run diagnostics without flashing or opening logs:

```sh
tools/zmk-flash-log.sh --diagnose COM12
```

## Artifact Resolution

When the first argument is an artifact name, the helper resolves it from the active workspace config:

```text
firmware/<config-folder>/<safe-branch>/<artifact>.uf2
```

For example:

```text
firmware/zmk-config-example/main/MY_KEYBOARD_RIGHT.uf2
```

If the current branch path does not contain the artifact, the helper searches `firmware/` for a unique matching file. If multiple files match, specify the UF2 path explicitly.

## Diagnostics

Use diagnostics before a remote flash/log session:

```sh
tools/zmk-flash-log.sh --diagnose COM12 --log-port COM12
```

The diagnostic output includes:

- UF2 path existence
- trigger port
- log port
- log baud rate
- bootloader baud rate
- visible Windows serial ports
- currently mounted UF2 loader drives
- warnings when the requested ports are not visible

This does not trigger the bootloader, copy firmware, or open the log port for capture.

## Safety

Use `ZMK_FLASH_BLOCKED_PORTS` or `--blocked-ports` to protect unrelated keyboards connected to the same PC.

```sh
ZMK_FLASH_BLOCKED_PORTS="COM3 COM4" tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12
```

or:

```sh
tools/zmk-flash-log.sh MY_KEYBOARD_RIGHT COM12 --blocked-ports "COM3 COM4"
```

## Important Options

- `--build`
  - Runs `./just.sh build <artifact>` before flashing.
- `--seconds <n>`
  - Captures serial logs for `n` seconds.
- `--log-port <COM>`
  - Uses a different serial port for logs.
- `--drive <letter>`
  - Restricts UF2 drive detection to a Windows drive letter.
- `--bootloader-baud <n>`
  - Defaults to `1200`.
- `--bootloader-delay-ms <n>`
  - Defaults to `300`.
- `--flash-timeout <n>`
  - Defaults to `60` seconds.
- `--post-flash-delay-ms <n>`
  - Defaults to `200`.

#!/bin/bash

#==============================================================================
# UF2 Flasher for macOS
#
# A script to automatically flash a given UF2 firmware file to a device
# connected in UF2 bootloader mode.
#==============================================================================

# Expect the full path to the UF2 file as the first argument
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_uf2_file> [target_mount_or_volume_name]"
    exit 1
fi

UF2_FILE="$1"
TARGET_HINT="${2:-}"

# Check if the firmware file exists
if [ ! -f "$UF2_FILE" ]; then
    echo "Error: File '$UF2_FILE' not found."
    exit 1
fi

echo "Firmware file: $UF2_FILE"
if [ -n "$TARGET_HINT" ]; then
    echo "Target mount hint: $TARGET_HINT"
fi

resolve_target_mount() {
    local hint="$1"
    if [ -z "$hint" ]; then
        return 1
    fi

    if [[ "$hint" == /Volumes/* ]]; then
        printf '%s\n' "$hint"
    else
        printf '/Volumes/%s\n' "$hint"
    fi
}

# Checks if a given mount point is a UF2 bootloader device
is_uf2_loader() {
    local mount_point="$1"
    if [ ! -d "$mount_point" ]; then
        return 1 # false
    fi

    if [ -f "${mount_point}/INFO_UF2.TXT" ] || [ -f "${mount_point}/INDEX.HTM" ]; then
        return 0 # true
    fi

    local volume_name
    volume_name=$(diskutil info "$mount_point" | grep "Volume Name:" | sed 's/.*Volume Name:[[:space:]]*//')
    if [[ "$volume_name" == *"UF2"* ]]; then
        return 0 # true
    fi

    return 1 # false
}

# Copies the firmware file to the target drive
write_firmware() {
    local target_mount_point="$1"
    local source_file="$2"
    echo "Copying firmware to drive at \"${target_mount_point}\"..."
    # Use COPYFILE_DISABLE to avoid copying extended attributes, which causes errors on FAT32/UF2 drives
    COPYFILE_DISABLE=1 cp "$source_file" "${target_mount_point}/"
    if [ $? -eq 0 ]; then
        echo "Flash completed!"
        sleep 2
    else
        echo "Error: Failed to copy firmware."
        exit 1
    fi
}

trap 'echo -e "\nCancelled by user."; exit 0' INT

# First, check already mounted drives
echo "Checking existing drives for UF2 loader..."
if [ -n "$TARGET_HINT" ]; then
    target_mount="$(resolve_target_mount "$TARGET_HINT")"
    if is_uf2_loader "$target_mount"; then
        echo "UF2 loader found at \"$target_mount\""
        write_firmware "$target_mount" "$UF2_FILE"
        exit 0
    fi
else
    for drive_path in /Volumes/*; do
        [ -e "$drive_path" ] || continue
        if is_uf2_loader "$drive_path"; then
            echo "UF2 loader found at \"$drive_path\""
            write_firmware "$drive_path" "$UF2_FILE"
            exit 0
        fi
    done
fi

# If not found, wait for a new drive to be connected
echo "No UF2 loader found. Waiting for new drive... (Press 'q' to cancel)"
before_drives_str=$(find /Volumes -maxdepth 1 -mindepth 1 -exec basename {} \;)

while true; do
    # Check for 'q' key press (non-blocking)
    if read -t 1 -n 1 key 2>/dev/null; then
        if [[ "$key" == "q" ]]; then
            echo -e "\nCancelled by user."
            exit 0
        fi
    fi

    after_drives_str=$(find /Volumes -maxdepth 1 -mindepth 1 -exec basename {} \;)
    new_drive_names=$(comm -13 <(echo "$before_drives_str" | sort) <(echo "$after_drives_str" | sort))

    if [ -n "$new_drive_names" ]; then
        while IFS= read -r drive; do
            [ -z "$drive" ] && continue
            echo "New drive detected: \"$drive\""
            mount_point="/Volumes/${drive}"
            if [ -n "$TARGET_HINT" ]; then
                target_mount="$(resolve_target_mount "$TARGET_HINT")"
                if [ "$mount_point" != "$target_mount" ]; then
                    echo "Drive \"$drive\" does not match target \"$TARGET_HINT\", skipping..."
                    continue
                fi
            fi
            sleep 1

            if is_uf2_loader "$mount_point"; then
                echo "UF2 loader detected at \"$mount_point\""
                write_firmware "$mount_point" "$UF2_FILE"
                exit 0
            else
                echo "Drive \"$drive\" is not a UF2 loader, skipping..."
            fi
        done <<< "$new_drive_names"
    fi
    before_drives_str=$after_drives_str
done

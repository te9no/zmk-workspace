# Get command line arguments
param(
    [Parameter(Mandatory=$false)]
    [string]$Uf2File,
    [Parameter(Mandatory=$false)]
    [string]$DriveLetter = ""
)

$ErrorActionPreference = "Stop"

# Check if the drive is a UF2 loader
function Test-IsUf2Loader {
    param([string]$DriveLetter)

    $drivePath = $DriveLetter + ":\"

    # Check if the drive is accessible
    if (-not (Test-Path $drivePath)) {
        return $false
    }

    try {
        # Get drive information
        $drive = Get-PSDrive -Name $DriveLetter -PSProvider FileSystem -ErrorAction SilentlyContinue
        if (-not $drive) {
            return $false
        }

        # Check the volume label
        $volume = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='${DriveLetter}:'" -ErrorAction SilentlyContinue
        if ($volume -and $volume.VolumeName -match "UF2") {
            return $true
        }

        # Check if the INFO_UF2.TXT file exists
        $infoFile = Join-Path $drivePath "INFO_UF2.TXT"
        if (Test-Path $infoFile) {
            return $true
        }

        # Check if the INDEX.HTM file exists (often found in UF2 loaders)
        $indexFile = Join-Path $drivePath "INDEX.HTM"
        if (Test-Path $indexFile) {
            return $true
        }

        return $false
    }
    catch {
        return $false
    }
}

function Write-Firmware {
    param([string]$TargetDrive, [string]$SourceFile)

    $targetPath = Join-Path ($TargetDrive + ":\") (Split-Path $SourceFile -Leaf)

    Write-Host "Copying firmware to drive $TargetDrive..."

    Copy-Item -LiteralPath $SourceFile -Destination $targetPath -Force -ErrorAction Stop

    Write-Host "Flash completed!"
}

function Select-SingleUf2Drive {
    param(
        [object[]]$Drives,
        [string]$RequestedDrive = ""
    )

    $candidates = @($Drives | Where-Object {
        (-not $RequestedDrive -or $_.Name -eq $RequestedDrive) -and
        (Test-IsUf2Loader -DriveLetter $_.Name)
    })
    if ($candidates.Count -gt 1) {
        $names = ($candidates | ForEach-Object { $_.Name }) -join ", "
        throw "Multiple UF2 loaders found ($names). Specify -DriveLetter."
    }
    if ($candidates.Count -eq 1) { return $candidates[0] }
    return $null
}

function Invoke-Uf2Flash {
    param([string]$FirmwareFile, [string]$RequestedDrive = "")

    if (-not $FirmwareFile -or -not (Test-Path -LiteralPath $FirmwareFile -PathType Leaf)) {
        throw "File '$FirmwareFile' not found or is not a regular file."
    }

    Write-Host "Firmware file: $FirmwareFile"
    if ($RequestedDrive) {
        $RequestedDrive = $RequestedDrive.Trim().TrimEnd(":").ToUpper()
        Write-Host "Target drive hint: $RequestedDrive"
    }

# Check if there is a UF2 loader in the existing drives
Write-Host "Checking existing drives for UF2 loader..."
    $initialDrives = @(Get-PSDrive -PSProvider FileSystem)
    $existing = Select-SingleUf2Drive -Drives $initialDrives -RequestedDrive $RequestedDrive
    if ($existing) {
        Write-Host "UF2 loader found on drive $($existing.Name)"
        Write-Firmware -TargetDrive $existing.Name -SourceFile $FirmwareFile
        return 0
    }

Write-Host "No UF2 loader found in existing drives."
Write-Host "Waiting for new UF2 loader drive... (Press 'q' to cancel)"

    while ($true) {
        # Check if a key is pressed
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.KeyChar -eq 'q' -or $key.KeyChar -eq 'Q') {
                Write-Host "`nCancelled."
                return 130
            }
        }

        Start-Sleep -Milliseconds 100
        $currentDrives = @(Get-PSDrive -PSProvider FileSystem)

        if ($RequestedDrive) {
            $requestedLoader = Select-SingleUf2Drive -Drives $currentDrives -RequestedDrive $RequestedDrive
            if ($requestedLoader) {
                Write-Host "UF2 loader detected on drive $($requestedLoader.Name)"
                Write-Firmware -TargetDrive $requestedLoader.Name -SourceFile $FirmwareFile
                return 0
            }
            continue
        }

        # Detect new drives
        $newDrives = $currentDrives | Where-Object {
            $drive = $_
            -not ($initialDrives | Where-Object { $_.Name -eq $drive.Name })
        }

        if (@($newDrives).Count -gt 0) {
            $newLoader = Select-SingleUf2Drive -Drives @($newDrives) -RequestedDrive $RequestedDrive
            if ($newLoader) {
                Write-Host "UF2 loader detected on drive $($newLoader.Name)"
                Write-Firmware -TargetDrive $newLoader.Name -SourceFile $FirmwareFile
                return 0
            }

            # Keep the startup baseline fixed so a newly mounted drive is
            # rechecked if its UF2 marker appears slightly later.
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        $exitCode = Invoke-Uf2Flash -FirmwareFile $Uf2File -RequestedDrive $DriveLetter
        exit ([int]$exitCode)
    }
    catch {
        Write-Error "An error occurred: $_"
        exit 1
    }
}

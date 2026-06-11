param(
    [Parameter(Mandatory=$true)]
    [string]$Uf2File,

    [Parameter(Mandatory=$false)]
    [string]$TriggerPort = "",

    [Parameter(Mandatory=$false)]
    [string]$LogPort = "",

    [Parameter(Mandatory=$false)]
    [string]$DriveLetter = "",

    [Parameter(Mandatory=$false)]
    [string]$LogPath = "",

    [Parameter(Mandatory=$false)]
    [int]$LogSeconds = 60,

    [Parameter(Mandatory=$false)]
    [int]$LogBaudRate = 115200,

    [Parameter(Mandatory=$false)]
    [int]$BootloaderBaudRate = 1200,

    [Parameter(Mandatory=$false)]
    [int]$BootloaderDelayMs = 300,

    [Parameter(Mandatory=$false)]
    [int]$FlashTimeoutSeconds = 60,

    [Parameter(Mandatory=$false)]
    [int]$PostFlashLogDelayMs = 200,

    [Parameter(Mandatory=$false)]
    [switch]$SkipFlash,

    [Parameter(Mandatory=$false)]
    [switch]$SkipLog,

    [Parameter(Mandatory=$false)]
    [switch]$DiagnoseOnly
)

$ErrorActionPreference = "Stop"

function Normalize-ComPort {
    param([string]$Port)

    if ([string]::IsNullOrWhiteSpace($Port)) {
        return ""
    }

    $p = $Port.Trim().ToUpperInvariant()
    if ($p -notmatch '^COM\d+$') {
        throw "Invalid COM port '$Port'. Use a value like COM12."
    }

    return $p
}

function Test-IsUf2Loader {
    param([string]$DriveLetter)

    $drivePath = $DriveLetter + ":\"
    if (-not (Test-Path $drivePath)) {
        return $false
    }

    $volume = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='${DriveLetter}:'" -ErrorAction SilentlyContinue
    if ($volume -and $volume.VolumeName -match "UF2") {
        return $true
    }

    if (Test-Path (Join-Path $drivePath "INFO_UF2.TXT")) {
        return $true
    }

    if (Test-Path (Join-Path $drivePath "INDEX.HTM")) {
        return $true
    }

    return $false
}

function Find-Uf2Drive {
    param([string]$DriveHint)

    $normalizedHint = ""
    if (-not [string]::IsNullOrWhiteSpace($DriveHint)) {
        $normalizedHint = $DriveHint.Trim().TrimEnd(":").ToUpperInvariant()
    }

    foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
        if ($normalizedHint -and $drive.Name -ne $normalizedHint) {
            continue
        }

        if (Test-IsUf2Loader -DriveLetter $drive.Name) {
            return $drive.Name
        }
    }

    return ""
}

function Show-Diagnostics {
    param(
        [string]$Uf2Path,
        [string]$Trigger,
        [string]$Log,
        [string]$DriveHint,
        [int]$LogBaud,
        [int]$BootBaud
    )

    Write-Host "ZMK flash/log diagnostics"
    Write-Host "========================="
    Write-Host ""
    Write-Host "UF2 path: $Uf2Path"
    Write-Host "UF2 exists: $(Test-Path $Uf2Path)"
    Write-Host "TriggerPort: $Trigger"
    Write-Host "LogPort: $Log"
    Write-Host "LogBaudRate: $LogBaud"
    Write-Host "BootloaderBaudRate: $BootBaud"
    Write-Host "Drive hint: $DriveHint"
    Write-Host ""

    Write-Host "Serial ports:"
    $ports = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
    if ($ports.Count -eq 0) {
        Write-Host "  (none)"
    } else {
        foreach ($p in $ports) {
            $mark = ""
            if ($p -eq $Trigger) { $mark += " trigger" }
            if ($p -eq $Log) { $mark += " log" }
            Write-Host "  - $p$mark"
        }
    }
    Write-Host ""

    Write-Host "UF2 loader drives:"
    $found = $false
    foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
        $isUf2 = Test-IsUf2Loader -DriveLetter $drive.Name
        if ($isUf2) {
            $found = $true
            Write-Host "  - $($drive.Name):"
        }
    }
    if (-not $found) {
        Write-Host "  (none)"
    }
    Write-Host ""

    if ($Trigger -and -not ($ports -contains $Trigger)) {
        Write-Host "WARNING: TriggerPort $Trigger is not currently visible."
    }
    if ($Log -and -not ($ports -contains $Log)) {
        Write-Host "WARNING: LogPort $Log is not currently visible."
    }
}

function Invoke-BootloaderTrigger {
    param(
        [string]$Port,
        [int]$BaudRate,
        [int]$DelayMs
    )

    if ([string]::IsNullOrWhiteSpace($Port)) {
        Write-Host "No trigger port specified. Waiting for an already-mounted UF2 drive."
        return
    }

    Write-Host "Triggering bootloader on $Port at $BaudRate baud..."
    $serial = New-Object System.IO.Ports.SerialPort $Port, $BaudRate, 'None', 8, 'One'
    $serial.ReadTimeout = 500
    $serial.WriteTimeout = 500
    $serial.DtrEnable = $true
    $serial.RtsEnable = $true
    $serial.Open()
    Start-Sleep -Milliseconds $DelayMs
    $serial.DtrEnable = $false
    $serial.RtsEnable = $false
    Start-Sleep -Milliseconds $DelayMs
    $serial.Close()
    $serial.Dispose()
}

function Wait-Uf2Drive {
    param(
        [string]$DriveHint,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $drive = Find-Uf2Drive -DriveHint $DriveHint
        if ($drive) {
            return $drive
        }

        Start-Sleep -Milliseconds 250
    }

    throw "Timed out waiting for a UF2 bootloader drive."
}

function Copy-Uf2 {
    param(
        [string]$DriveLetter,
        [string]$SourceFile
    )

    $target = Join-Path ($DriveLetter + ":\") (Split-Path $SourceFile -Leaf)
    Write-Host "Copying firmware to ${DriveLetter}: ..."
    Copy-Item -Path $SourceFile -Destination $target -Force
    Write-Host "Firmware copy completed."
}

function Wait-SerialPort {
    param(
        [string]$Port,
        [int]$BaudRate,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null

    while ((Get-Date) -lt $deadline) {
        try {
            $serial = New-Object System.IO.Ports.SerialPort $Port, $BaudRate, 'None', 8, 'One'
            $serial.ReadTimeout = 500
            $serial.WriteTimeout = 500
            $serial.Open()
            return $serial
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 500
        }
    }

    throw "Timed out opening $Port for logging. Last error: $lastError"
}

function Capture-SerialLog {
    param(
        [string]$Port,
        [int]$BaudRate,
        [string]$OutputPath,
        [int]$Seconds
    )

    if ([string]::IsNullOrWhiteSpace($Port)) {
        Write-Host "No log port specified. Skipping log capture."
        return
    }

    if ($Seconds -le 0) {
        Write-Host "LogSeconds is 0. Skipping log capture."
        return
    }

    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    if (-not (Test-Path $OutputPath)) {
        New-Item -ItemType File -Path $OutputPath | Out-Null
    }

    Write-Host "Opening $Port at $BaudRate baud for $Seconds seconds..."
    $serial = Wait-SerialPort -Port $Port -BaudRate $BaudRate -TimeoutSeconds 30
    try {
        $deadline = (Get-Date).AddSeconds($Seconds)
        while ((Get-Date) -lt $deadline) {
            try {
                $line = $serial.ReadLine()
                $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
                $entry = "[$timestamp] $line"
                Add-Content -Path $OutputPath -Value $entry
                Write-Host $entry
            }
            catch [System.TimeoutException] {
                continue
            }
        }
    }
    finally {
        if ($serial.IsOpen) {
            $serial.Close()
        }
        $serial.Dispose()
    }

    Write-Host "Log captured at $OutputPath"
}

$TriggerPort = Normalize-ComPort $TriggerPort
$LogPort = Normalize-ComPort $LogPort
if (-not $LogPort) {
    $LogPort = $TriggerPort
}

if (-not (Test-Path $Uf2File)) {
    throw "UF2 file not found: $Uf2File"
}

if (-not $LogPath) {
    $name = [IO.Path]::GetFileNameWithoutExtension($Uf2File)
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $LogPath = Join-Path (Join-Path (Get-Location) "logs") "$name-$stamp.log"
}

Write-Host "UF2: $Uf2File"
Write-Host "TriggerPort: $TriggerPort"
Write-Host "LogPort: $LogPort"
Write-Host "LogPath: $LogPath"

if ($DiagnoseOnly) {
    Show-Diagnostics -Uf2Path $Uf2File -Trigger $TriggerPort -Log $LogPort -DriveHint $DriveLetter -LogBaud $LogBaudRate -BootBaud $BootloaderBaudRate
    exit 0
}

if (-not $SkipFlash) {
    Invoke-BootloaderTrigger -Port $TriggerPort -BaudRate $BootloaderBaudRate -DelayMs $BootloaderDelayMs
    $drive = Wait-Uf2Drive -DriveHint $DriveLetter -TimeoutSeconds $FlashTimeoutSeconds
    Write-Host "UF2 drive found: ${drive}:"
    Copy-Uf2 -DriveLetter $drive -SourceFile $Uf2File
}

if (-not $SkipLog) {
    if ($PostFlashLogDelayMs -gt 0) {
        Start-Sleep -Milliseconds $PostFlashLogDelayMs
    }
    Capture-SerialLog -Port $LogPort -BaudRate $LogBaudRate -OutputPath $LogPath -Seconds $LogSeconds
}

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

& {
    . (Join-Path $repo "flash.ps1")
    function Test-IsUf2Loader { param([string]$DriveLetter) return $true }

    $drives = @(
        [pscustomobject]@{ Name = "E" },
        [pscustomobject]@{ Name = "F" }
    )
    $rejected = $false
    try { Select-SingleUf2Drive -Drives $drives | Out-Null } catch { $rejected = $true }
    Assert-True $rejected "Multiple PowerShell drives were not rejected."

    $selected = Select-SingleUf2Drive -Drives $drives -RequestedDrive "F"
    Assert-True ($selected.Name -eq "F") "Explicit PowerShell drive was not selected."

    function Copy-Item { throw "simulated copy failure" }
    $output = @()
    $copyFailed = $false
    try { $output = @(Write-Firmware -TargetDrive "F" -SourceFile "fixture.uf2" *>&1) }
    catch { $copyFailed = $true }
    Assert-True $copyFailed "Copy failure did not propagate."
    Assert-True (-not (($output | Out-String) -match "Flash completed")) "Copy failure printed success."
}

& {
    . (Join-Path $repo "tools/zmk-flash-log.ps1")
    Assert-True ((Select-SingleUf2Drive -Candidates @()) -eq "") "Empty candidate set was not empty."
    Assert-True ((Select-SingleUf2Drive -Candidates @("G")) -eq "G") "Single helper drive was not selected."
    $rejected = $false
    try { Select-SingleUf2Drive -Candidates @("G", "H") | Out-Null } catch { $rejected = $true }
    Assert-True $rejected "Multiple helper drives were not rejected."

    $baseline = @("E", "F")
    $current = @("E", "F", "G")
    $new = @($current | Where-Object { $baseline -notcontains $_ })
    Assert-True ((Select-SingleUf2Drive -Candidates $new) -eq "G") "New-only helper drive selection failed."
}

Write-Output "PowerShell flash safety tests passed."

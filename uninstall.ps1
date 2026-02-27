[CmdletBinding()]
param(
    [string]$RuntimeRoot,
    [switch]$KeepEnvVars
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd("\")
}

function First-NonEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [AllowNull()]
        [AllowEmptyString()]
        [string[]]$Values
    )

    foreach ($v in $Values) {
        if (-not [string]::IsNullOrWhiteSpace($v)) {
            return $v.Trim()
        }
    }

    return $null
}

function Test-ContainsText {
    param(
        [AllowNull()]
        [string]$Text,
        [Parameter(Mandatory = $true)]
        [string]$Needle
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }

    return $Text.IndexOf($Needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Clear-ReadOnlyRecursive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }

    $rootItem = Get-Item -LiteralPath $PathValue -Force
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReadOnly) {
        $rootItem.Attributes = $rootItem.Attributes -bxor [IO.FileAttributes]::ReadOnly
    }

    if ($rootItem.PSIsContainer) {
        Get-ChildItem -LiteralPath $PathValue -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.Attributes -band [IO.FileAttributes]::ReadOnly) {
                $_.Attributes = $_.Attributes -bxor [IO.FileAttributes]::ReadOnly
            }
        }
    }
}

function Remove-PathIfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        Write-Host "[SKIP] Tidak ditemukan: $PathValue"
        return
    }

    Clear-ReadOnlyRecursive -PathValue $PathValue
    Remove-Item -LiteralPath $PathValue -Recurse -Force -ErrorAction Stop
    Write-Host "[OK] Terhapus: $PathValue"
}

function Remove-EnvVarIfMatchesRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [ValidateSet("Process", "User", "Machine")]
        [string]$Scope,
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    $target = [System.EnvironmentVariableTarget]::$Scope
    $value = [Environment]::GetEnvironmentVariable($Name, $target)

    if ([string]::IsNullOrWhiteSpace($value)) {
        return
    }

    $normalizedValue = Normalize-Path -PathValue $value
    if ($normalizedValue -ine $RootPath) {
        return
    }

    try {
        [Environment]::SetEnvironmentVariable($Name, $null, $target)
        Write-Host "[OK] Env $Name ($Scope) dihapus"
    }
    catch {
        Write-Warning "Gagal menghapus env $Name ($Scope): $($_.Exception.Message)"
    }
}

function Stop-RelatedProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    $selfPid = $PID
    $excluded = @("powershell.exe", "pwsh.exe", "conhost.exe")
    $killed = 0

    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    if (-not $processes) {
        return
    }

    $byPid = @{}
    $childrenByParent = @{}
    foreach ($p in $processes) {
        $processId = [int]$p.ProcessId
        $parentPid = [int]$p.ParentProcessId
        $byPid[$processId] = $p

        if (-not $childrenByParent.ContainsKey($parentPid)) {
            $childrenByParent[$parentPid] = New-Object System.Collections.Generic.List[int]
        }
        [void]$childrenByParent[$parentPid].Add($processId)
    }

    $seedPids = New-Object System.Collections.Generic.HashSet[int]
    foreach ($p in $processes) {
        $processId = [int]$p.ProcessId
        if ($processId -eq $selfPid) {
            continue
        }

        $inRoot = (Test-ContainsText -Text $p.ExecutablePath -Needle $RootPath) -or (Test-ContainsText -Text $p.CommandLine -Needle $RootPath)
        if ($inRoot) {
            [void]$seedPids.Add($processId)
        }
    }

    $targetPids = New-Object System.Collections.Generic.HashSet[int]
    $queue = New-Object System.Collections.Generic.Queue[int]

    foreach ($seedProcessId in $seedPids) {
        [void]$targetPids.Add($seedProcessId)
        $queue.Enqueue($seedProcessId)
    }

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if (-not $childrenByParent.ContainsKey($current)) {
            continue
        }

        foreach ($childPid in $childrenByParent[$current]) {
            if ($targetPids.Add($childPid)) {
                $queue.Enqueue($childPid)
            }
        }
    }

    foreach ($targetProcessId in ($targetPids | Sort-Object -Descending)) {
        if ($targetProcessId -eq $selfPid -or -not $byPid.ContainsKey($targetProcessId)) {
            continue
        }

        $p = $byPid[$targetProcessId]
        $nameValue = ""
        if ($null -ne $p.Name) {
            $nameValue = [string]$p.Name
        }
        $name = $nameValue.ToLowerInvariant()
        if ($excluded -contains $name) {
            continue
        }

        try {
            Stop-Process -Id $targetProcessId -Force -ErrorAction Stop
            Write-Host "[OK] Stop process $($p.Name) (PID $targetProcessId)"
            $killed++
        }
        catch {
            Write-Warning "Gagal stop PID ${targetProcessId}: $($_.Exception.Message)"
        }
    }

    if ($killed -gt 0) {
        Start-Sleep -Milliseconds 700
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidateRoot = First-NonEmpty -Values @(
    $RuntimeRoot,
    $env:VIMO_ROOT,
    $env:VIMO_CONFIG_DIR,
    [Environment]::GetEnvironmentVariable("VIMO_ROOT", "User"),
    [Environment]::GetEnvironmentVariable("VIMO_ROOT", "Machine"),
    [Environment]::GetEnvironmentVariable("VIMO_CONFIG_DIR", "User"),
    [Environment]::GetEnvironmentVariable("VIMO_CONFIG_DIR", "Machine"),
    $scriptDir
)

$resolvedRoot = Normalize-Path -PathValue $candidateRoot
Write-Host "Runtime root: $resolvedRoot"

Stop-RelatedProcesses -RootPath $resolvedRoot

$pathsToDelete = @(
    (Join-Path $resolvedRoot ".env"),
    (Join-Path $resolvedRoot "connection.json"),
    (Join-Path $resolvedRoot "storage")
)

foreach ($p in $pathsToDelete) {
    Remove-PathIfExists -PathValue $p
}

# Legacy runtime config path used by old versions.
$legacyConfigFile = Join-Path $env:APPDATA "Vimo\config\connection.json"
$legacyConfigDir = Join-Path $env:APPDATA "Vimo\config"
$legacyRootDir = Join-Path $env:APPDATA "Vimo"

Remove-PathIfExists -PathValue $legacyConfigFile
if (Test-Path -LiteralPath $legacyConfigDir) {
    $remainingInConfig = Get-ChildItem -LiteralPath $legacyConfigDir -Force -ErrorAction SilentlyContinue
    if (-not $remainingInConfig) {
        Remove-PathIfExists -PathValue $legacyConfigDir
    }
}
if (Test-Path -LiteralPath $legacyRootDir) {
    $remainingInLegacyRoot = Get-ChildItem -LiteralPath $legacyRootDir -Force -ErrorAction SilentlyContinue
    if (-not $remainingInLegacyRoot) {
        Remove-PathIfExists -PathValue $legacyRootDir
    }
}

if (-not $KeepEnvVars) {
    Remove-EnvVarIfMatchesRoot -Name "VIMO_ROOT" -Scope "Process" -RootPath $resolvedRoot
    Remove-EnvVarIfMatchesRoot -Name "VIMO_ROOT" -Scope "User" -RootPath $resolvedRoot
    Remove-EnvVarIfMatchesRoot -Name "VIMO_ROOT" -Scope "Machine" -RootPath $resolvedRoot
    Remove-EnvVarIfMatchesRoot -Name "VIMO_CONFIG_DIR" -Scope "Process" -RootPath $resolvedRoot
    Remove-EnvVarIfMatchesRoot -Name "VIMO_CONFIG_DIR" -Scope "User" -RootPath $resolvedRoot
    Remove-EnvVarIfMatchesRoot -Name "VIMO_CONFIG_DIR" -Scope "Machine" -RootPath $resolvedRoot
}

Write-Host ""
Write-Host "Uninstall data/config selesai."

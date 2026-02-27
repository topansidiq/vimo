[CmdletBinding()]
param(
    [switch]$Prepare,
    [ValidateSet("local", "hivemq")]
    [string]$Broker = "local",
    [switch]$ForceEnv,
    [switch]$NonInteractive,
    [string]$IsccPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-IsccPath {
    param(
        [string]$PreferredPath
    )

    $candidates = New-Object System.Collections.Generic.List[string]

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
        [void]$candidates.Add($PreferredPath)
    }

    $isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
    if ($null -ne $isccCommand -and -not [string]::IsNullOrWhiteSpace($isccCommand.Source)) {
        [void]$candidates.Add($isccCommand.Source)
    }

    [void]$candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"))
    [void]$candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))

    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "ISCC.exe tidak ditemukan. Install Inno Setup 6 atau kirim path via -IsccPath."
}

$installerDir = (Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$repoRoot = (Resolve-Path (Join-Path $installerDir "..")).Path
$issFile = Join-Path $installerDir "vimo.iss"
$distDir = Join-Path $installerDir "dist"
$desktopExe = Join-Path $repoRoot "vimo\dist\Vimo.exe"
$setupScript = Join-Path $repoRoot "setup.ps1"

if (-not (Test-Path -LiteralPath $issFile)) {
    throw "File Inno Setup tidak ditemukan: $issFile"
}

if ($Prepare) {
    if (-not (Test-Path -LiteralPath $setupScript)) {
        throw "Script setup tidak ditemukan: $setupScript"
    }

    Write-Host ""
    Write-Host "== Prepare build assets ==" -ForegroundColor Cyan

    $setupArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($Broker)) {
        $setupArgs += "-Broker"
        $setupArgs += $Broker
    }
    if ($ForceEnv) {
        $setupArgs += "-ForceEnv"
    }
    if ($NonInteractive) {
        $setupArgs += "-NonInteractive"
    }

    & $setupScript @setupArgs
}

if (-not (Test-Path -LiteralPath $desktopExe)) {
    throw "Desktop binary belum ada: $desktopExe`nJalankan build dulu (mis. .\\setup.ps1) atau pakai -Prepare."
}

if (-not (Test-Path -LiteralPath $distDir)) {
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
}

$iscc = Resolve-IsccPath -PreferredPath $IsccPath

Write-Host ""
Write-Host "== Build setup.exe ==" -ForegroundColor Cyan
Write-Host "ISCC    : $iscc"
Write-Host "ISS     : $issFile"
Write-Host "Repo    : $repoRoot"
Write-Host "Output  : $distDir"

& $iscc "/DRepoRoot=$repoRoot" "/DOutputDir=$distDir" $issFile
if ($LASTEXITCODE -ne 0) {
    throw "ISCC gagal dengan exit code $LASTEXITCODE"
}

$setupOutput = Join-Path $distDir "VimoSetup.exe"
if (Test-Path -LiteralPath $setupOutput) {
    Write-Host ""
    Write-Host "Selesai: $setupOutput" -ForegroundColor Green
}
else {
    Write-Warning "Build selesai tapi file VimoSetup.exe tidak ditemukan di $distDir"
}

param(
    [switch]$OneFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

$VenvPath = Join-Path $RepoRoot ".venv-build"
if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$Python = Join-Path $VenvPath "Scripts\\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python venv executable not found at $Python"
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-production.txt

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

$PyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "Vimo",
    "--collect-submodules", "qtawesome",
    "--hidden-import", "matplotlib.backends.backend_qt5agg",
    "main.py"
)

if ($OneFile) {
    $PyInstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name", "Vimo",
        "--collect-submodules", "qtawesome",
        "--hidden-import", "matplotlib.backends.backend_qt5agg",
        "main.py"
    )
}

& $Python @PyInstallerArgs

Write-Host "Build selesai. Output ada di folder dist/."

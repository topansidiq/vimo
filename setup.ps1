[CmdletBinding()]
param(
    [ValidateSet("local", "hivemq")]
    [string]$Broker,
    [switch]$ForceEnv,
    [switch]$SkipBuild,
    [switch]$SkipServerInstall,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ServerDir = Join-Path $RootDir "server"
$VimoDir = Join-Path $RootDir "vimo"
$VenvDir = Join-Path $VimoDir ".venv-build"

function Assert-CommandExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name tidak ditemukan. $InstallHint"
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    & $Action
}

function Resolve-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Exe = "python"
            Prefix = @()
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            Exe = "py"
            Prefix = @("-3")
        }
    }

    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        return @{
            Exe = "python3"
            Prefix = @()
        }
    }

    throw "Python tidak ditemukan. Install Python 3.9+ terlebih dahulu."
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & $script:PythonExe @script:PythonPrefix @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Perintah python gagal: $($Args -join ' ')"
    }
}

Assert-CommandExists -Name "node" -InstallHint "Install Node.js LTS terlebih dahulu."
if (-not $SkipServerInstall) {
    Assert-CommandExists -Name "npm" -InstallHint "Install npm terlebih dahulu."
}

$script:PythonExe = $null
$script:PythonPrefix = @()
$script:VenvPython = $null
if (-not $SkipBuild) {
    $pythonInfo = Resolve-PythonCommand
    $script:PythonExe = $pythonInfo.Exe
    $script:PythonPrefix = $pythonInfo.Prefix
}

Invoke-Step -Label "Step 1/5: Install server dependencies" -Action {
    if ($SkipServerInstall) {
        Write-Host "Lewati npm install (SkipServerInstall aktif)." -ForegroundColor Yellow
        return
    }

    Push-Location $ServerDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install gagal."
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Label "Step 2/5: Generate root .env" -Action {
    $setupEnvScript = Join-Path $ServerDir "scripts\setup-env.js"
    $envArgs = @($setupEnvScript)

    if ($Broker) {
        $envArgs += "--broker=$Broker"
    }
    if ($ForceEnv) {
        $envArgs += "--force"
    }
    if ($NonInteractive) {
        $envArgs += "--yes"
    }

    & node @envArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Gagal generate root file .env."
    }
}

Invoke-Step -Label "Step 3/5: Prepare Python build environment" -Action {
    if ($SkipBuild) {
        Write-Host "Lewati setup Python build environment (SkipBuild aktif)." -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path $VenvDir)) {
        Invoke-Python -Args @("-m", "venv", $VenvDir)
    }

    $venvPythonWindows = Join-Path $VenvDir "Scripts\python.exe"
    $venvPythonUnix = Join-Path $VenvDir "bin\python"

    if (Test-Path $venvPythonWindows) {
        $script:VenvPython = $venvPythonWindows
    }
    elseif (Test-Path $venvPythonUnix) {
        $script:VenvPython = $venvPythonUnix
    }
    else {
        throw "Python venv executable tidak ditemukan di $VenvDir"
    }

    & $script:VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Upgrade pip gagal."
    }

    & $script:VenvPython -m pip install -r (Join-Path $VimoDir "requirements-production.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Install Python requirements gagal."
    }
}

Invoke-Step -Label "Step 4/5: Ensure root storage and config" -Action {
    New-Item -ItemType Directory -Path (Join-Path $RootDir "storage\private") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $RootDir "storage\logs") -Force | Out-Null

    $rootConfig = Join-Path $RootDir "connection.json"
    $configExample = Join-Path $VimoDir "core\connection.example.json"
    if (-not (Test-Path $rootConfig) -and (Test-Path $configExample)) {
        Copy-Item -Path $configExample -Destination $rootConfig
    }
}

Invoke-Step -Label "Step 5/5: Build desktop one-file app" -Action {
    if ($SkipBuild) {
        Write-Host "Lewati build desktop app (SkipBuild aktif)." -ForegroundColor Yellow
        return
    }

    Push-Location $VimoDir
    try {
        & $script:VenvPython -m PyInstaller `
            --noconfirm `
            --clean `
            --windowed `
            --onefile `
            --name Vimo `
            --collect-submodules qtawesome `
            --hidden-import matplotlib.backends.backend_qt5agg `
            main.py

        if ($LASTEXITCODE -ne 0) {
            throw "Build PyInstaller gagal."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Setup selesai." -ForegroundColor Green
Write-Host "Runtime root  : $RootDir"
Write-Host "Server env    : $(Join-Path $RootDir '.env')"
Write-Host "App config    : $(Join-Path $RootDir 'connection.json')"
Write-Host "Storage path  : $(Join-Path $RootDir 'storage')"
Write-Host "Start server  : cd server; npm run start"

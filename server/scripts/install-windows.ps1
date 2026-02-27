param(
    [ValidateSet("local", "hivemq")]
    [string]$Broker
)

$ErrorActionPreference = "Stop"

$rootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $rootDir

function Assert-CommandExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name tidak ditemukan. $InstallHint"
        exit 1
    }
}

function Run-Step {
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

Assert-CommandExists -Name "node" -InstallHint "Install Node.js LTS terlebih dahulu."
Assert-CommandExists -Name "npm" -InstallHint "Install npm (biasanya sudah ikut Node.js)."

Write-Host "Installer Vimo Server (Windows)" -ForegroundColor Green

if (-not $Broker) {
    Write-Host ""
    Write-Host "Pilih broker MQTT:"
    Write-Host "1. Local Mosquitto"
    Write-Host "2. HiveMQ Cloud"

    while ($true) {
        $choice = (Read-Host "Masukkan pilihan [1/2]").Trim().ToLower()
        if ($choice -eq "1" -or $choice -eq "local" -or $choice -eq "mosquitto") {
            $Broker = "local"
            break
        }

        if ($choice -eq "2" -or $choice -eq "hivemq") {
            $Broker = "hivemq"
            break
        }

        Write-Host "Pilihan tidak valid, ulangi lagi." -ForegroundColor Yellow
    }
}

Run-Step -Label "Install dependency npm" -Action {
    npm install
    if ($LASTEXITCODE -ne 0) {
        throw "npm install gagal."
    }
}

if ($Broker -eq "local") {
    Run-Step -Label "Opsional install Mosquitto" -Action {
        $installMosquitto = (Read-Host "Install Mosquitto broker via winget sekarang? [Y/n]").Trim().ToLower()

        if (-not $installMosquitto -or $installMosquitto -eq "y" -or $installMosquitto -eq "yes") {
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                winget install -e --id EclipseMosquitto.Mosquitto --accept-package-agreements --accept-source-agreements
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Install Mosquitto via winget gagal. Lanjutkan instalasi manual jika perlu."
                }
            } else {
                Write-Warning "winget tidak tersedia. Install Mosquitto manual dari https://mosquitto.org/download/."
            }
        } else {
            Write-Host "Lewati install Mosquitto."
        }

        try {
            $service = Get-Service -Name "mosquitto" -ErrorAction SilentlyContinue
            if ($service) {
                if ($service.Status -ne "Running") {
                    Start-Service -Name "mosquitto" -ErrorAction SilentlyContinue
                }
                Write-Host "Service mosquitto siap dipakai."
            } else {
                Write-Host "Service mosquitto belum ditemukan. Silakan jalankan broker manual jika diperlukan."
            }
        } catch {
            Write-Warning "Tidak bisa mengaktifkan service mosquitto otomatis. Jalankan manual jika diperlukan."
        }
    }
}

Run-Step -Label "Generate root file .env" -Action {
    node .\scripts\setup-env.js --broker=$Broker --force
    if ($LASTEXITCODE -ne 0) {
        throw "Gagal membuat root file .env"
    }
}

Write-Host ""
Write-Host "Setup selesai." -ForegroundColor Green
Write-Host "Jalankan server:"
Write-Host "  npm run start"

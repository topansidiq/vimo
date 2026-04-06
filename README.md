# Vimo

Vimo adalah sistem monitoring mesin berbasis sensor (MPU6050) yang terdiri dari:

- Desktop app (`vimo/`) berbasis Python + PyQt5 untuk dashboard, activity, log, dan pengaturan koneksi.
- Backend server (`server/`) berbasis Node.js untuk API, MQTT bridge, dan penyimpanan SQLite.
- Installer Windows (`installer/`) berbasis Inno Setup untuk menghasilkan `VimoSetup.exe`.
- Firmware contoh (`ino/`) untuk perangkat sensor.

## Fitur Utama

- Monitoring data sensor real-time (accelerometer/gyroscope).
- Manajemen perangkat dan aset.
- Log aktivitas dan statistik.
- Koneksi server configurable dari desktop app.
- Build one-file desktop app dan packaging installer `.exe`.

## Prasyarat

- Windows 10/11 x64 (untuk jalur installer).
- Node.js LTS.
- Python 3.9+.
- MQTT broker (default local Mosquitto `localhost:1883`).
- Inno Setup 6 (hanya jika ingin build installer).

## Quick Start

### Opsi 1: Pakai Installer (paling cepat)

1. Jalankan `installer\dist\VimoSetup.exe` sebagai Administrator.
2. Selesaikan wizard instalasi.
3. Jalankan shortcut:
   - `Vimo Bootstrap` (sekali untuk setup `.env` dan `storage`)
   - `Vimo Server`
   - `Vimo`

### Opsi 2: Jalankan dari source

Dari root project:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Broker local -ForceEnv
```

Lalu jalankan server:

```powershell
cd server
npm run start
```

Jalankan desktop app:

```powershell
.\vimo\dist\Vimo.exe
```

## Konfigurasi Wajib di Desktop App

Masuk ke **Settings -> Server Connection**:

- Host: `127.0.0.1` (atau IP server)
- Port: sesuai `APP_PORT` pada `.env` (default `3001`)
- Simpan, lalu klik **Connect to Server**

## Build dan Packaging

### Build desktop one-file

```powershell
cd vimo
.\scripts\build-production.ps1 -OneFile
```

Output: `vimo\dist\Vimo.exe`

### Build installer setup.exe

Dari root project:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build-setup-exe.ps1 -Prepare -Broker local -ForceEnv
```

Output: `installer\dist\VimoSetup.exe`

## Lokasi File Runtime (root project)

- `.env`
- `connection.json`
- `storage\private\app.db`
- `storage\logs\`

## Struktur Proyek

```text
Vimo/
|- .github/workflows/        # CI/CD release
|- installer/                # Script dan spec Inno Setup
|- ino/                      # Firmware sensor contoh
|- server/                   # Backend Node.js (API, MQTT, SQLite)
|- vimo/                     # Desktop app Python/PyQt5
|- setup.ps1                 # Setup bundling flow (Windows)
|- setup.sh                  # Setup bundling flow (Linux)
|- uninstall.ps1             # Cleanup runtime data/config
`- how_to_install.txt        # Panduan install ringkas
```

## Troubleshooting Singkat

- Tidak bisa connect ke server:
  - Pastikan `npm run start` aktif.
  - Pastikan port `APP_PORT` tidak bentrok.
  - Pastikan broker MQTT aktif dan konfigurasi `.env` benar.
- `VimoSetup.exe` belum ada:
  - Build dulu lewat `installer\build-setup-exe.ps1`.

## Dokumen Terkait

- `vimo/PRODUCTION.md`
- `server/README.md`
- `how_to_install.txt`

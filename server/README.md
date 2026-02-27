# Vimo Server - Production Local Setup

Dokumentasi ini fokus untuk menjalankan aplikasi secara lokal dengan mode production-like, plus opsi broker MQTT:
- Local Mosquitto
- Online broker HiveMQ Cloud

## Prasyarat

- Node.js LTS (disarankan 20+)
- npm

## Installer Windows

Jalankan dari root project:

```powershell
npm run setup:windows
```

Atau langsung:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

Installer akan:
- install dependency npm
- meminta pilihan broker MQTT (Local Mosquitto atau HiveMQ)
- (opsional) install Mosquitto via `winget`
- generate file root `.env` (`../.env`) dengan konfigurasi yang sesuai

## Installer Linux

Berikan izin eksekusi lalu jalankan installer:

```bash
chmod +x scripts/install-linux.sh
npm run setup:linux
```

Atau langsung:

```bash
./scripts/install-linux.sh
```

Installer akan:
- install dependency npm
- meminta pilihan broker MQTT
- (opsional) install Mosquitto dari package manager distro
- generate file root `.env` (`../.env`)

## Setup Env Manual

Jika ingin membuat root `.env` tanpa installer OS:

```bash
npm run setup:env
```

Argumen tambahan:
- `--broker=local` atau `--broker=hivemq`
- `--force` untuk overwrite root `.env`
- `--yes` untuk non-interactive (default value)
- `--output=.env.production` untuk output file lain

Contoh:

```bash
node scripts/setup-env.js --broker=local --force
```

## Menjalankan Server

```bash
npm run start
```

Health check root endpoint:

```bash
curl http://localhost:3001/
```

Response akan menampilkan status MQTT aktual, provider, broker, dan topic subscription.

## Lokasi runtime

- Env file: `<project-root>/.env`
- SQLite DB: `<project-root>/storage/private/app.db`
- Server logs: `<project-root>/storage/logs/app-YYYY-MM-DD.log`

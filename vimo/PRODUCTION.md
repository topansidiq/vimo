# Production Guide

## 1. Runtime directory model

Runtime now uses app root directly.

- Default runtime root:
  - Source mode: project root (`.../Vimo`)
  - Frozen build: folder of executable
- Config file: `<root>/connection.json`
- Data files: `<root>/storage/devices.json`, `<root>/storage/assets.json`
- Logs: `<root>/storage/logs/vimo.log`

Override runtime root (optional):

```powershell
$env:VIMO_ROOT = "D:\\VimoRuntime"
```

```bash
export VIMO_ROOT=/opt/vimo-runtime
```

## 2. One-file setup (bundle flow)

From project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Broker local -ForceEnv
```

```bash
./setup.sh
```

This performs:

1. Server dependency install (`server/node_modules`)
2. Root `.env` generation (`<root>/.env`)
3. Python build environment setup
4. Root runtime bootstrap (`connection.json`, `storage/`)
5. Desktop one-file build (`vimo/dist/Vimo*`)

## 3. Manual build (desktop only)

```powershell
.\scripts\build-production.ps1 -OneFile
```

Output:

- One-file build: `dist\\Vimo.exe`

## 4. Packaging to setup.exe (Windows)

Requirement:

- Inno Setup 6 (`ISCC.exe`) installed.

Build command:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build-setup-exe.ps1 -Prepare -Broker local -ForceEnv
```

Output:

- `installer\\dist\\VimoSetup.exe`

## 5. Operational checks

Before go-live, verify:

1. App can connect/disconnect to server from **Settings**.
2. Logs are generated in `<root>/storage/logs`.
3. Device and asset data persist after restart.
4. `.env` and `connection.json` exist in root directory.

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
VIMO_DIR="$ROOT_DIR/vimo"
VENV_DIR="$VIMO_DIR/.venv-build"
BUILD_APP="true"
FORCE_ENV="false"
BROKER=""

usage() {
  cat <<'EOF'
Usage: ./setup.sh [options]

Options:
  --broker=local|hivemq   Set MQTT broker mode for .env generation.
  --force-env             Overwrite existing root .env without prompt.
  --skip-build            Skip PyInstaller one-file build for desktop app.
  -h, --help              Show this help.
EOF
}

require_command() {
  local command_name="$1"
  local hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: $command_name not found. $hint" >&2
    exit 1
  fi
}

resolve_python() {
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi

  echo ""
}

for arg in "$@"; do
  case "$arg" in
    --broker=*)
      BROKER="${arg#*=}"
      ;;
    --force-env)
      FORCE_ENV="true"
      ;;
    --skip-build)
      BUILD_APP="false"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$BROKER" && "$BROKER" != "local" && "$BROKER" != "hivemq" ]]; then
  echo "Error: --broker must be local or hivemq." >&2
  exit 1
fi

require_command node "Install Node.js LTS first."
require_command npm "Install npm first."

PYTHON_CMD="$(resolve_python)"
if [[ -z "$PYTHON_CMD" ]]; then
  echo "Error: python/python3 not found. Install Python 3.9+ first." >&2
  exit 1
fi

echo
echo "== Step 1/5: Install server dependencies =="
(
  cd "$SERVER_DIR"
  npm install
)

echo
echo "== Step 2/5: Generate root .env =="
env_cmd=(node "$SERVER_DIR/scripts/setup-env.js")
if [[ -n "$BROKER" ]]; then
  env_cmd+=("--broker=$BROKER")
fi
if [[ "$FORCE_ENV" == "true" ]]; then
  env_cmd+=("--force")
fi
"${env_cmd[@]}"

echo
echo "== Step 3/5: Prepare Python build environment =="
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

if [[ -x "$VENV_DIR/bin/python" ]]; then
  VENV_PYTHON="$VENV_DIR/bin/python"
else
  VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$VIMO_DIR/requirements-production.txt"

echo
echo "== Step 4/5: Ensure runtime root storage/config =="
mkdir -p "$ROOT_DIR/storage/private" "$ROOT_DIR/storage/logs"
if [[ ! -f "$ROOT_DIR/connection.json" && -f "$VIMO_DIR/core/connection.example.json" ]]; then
  cp "$VIMO_DIR/core/connection.example.json" "$ROOT_DIR/connection.json"
fi

echo
echo "== Step 5/5: Build desktop one-file app =="
if [[ "$BUILD_APP" == "true" ]]; then
  (
    cd "$VIMO_DIR"
    "$VENV_PYTHON" -m PyInstaller \
      --noconfirm \
      --clean \
      --windowed \
      --onefile \
      --name Vimo \
      --collect-submodules qtawesome \
      --hidden-import matplotlib.backends.backend_qt5agg \
      main.py
  )
  echo "Desktop build complete: $VIMO_DIR/dist"
else
  echo "Skipped desktop build (--skip-build)."
fi

echo
echo "Setup complete."
echo "Runtime root  : $ROOT_DIR"
echo "Server env    : $ROOT_DIR/.env"
echo "App config    : $ROOT_DIR/connection.json"
echo "Storage path  : $ROOT_DIR/storage"
echo "Start server  : cd server && npm run start"


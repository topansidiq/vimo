#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BROKER="${1:-}"

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: $command_name tidak ditemukan. $install_hint" >&2
    exit 1
  fi
}

choose_broker() {
  echo
  echo "Pilih broker MQTT:"
  echo "1. Local Mosquitto"
  echo "2. HiveMQ Cloud"

  while true; do
    read -r -p "Masukkan pilihan [1/2]: " choice
    case "${choice,,}" in
      1|local|mosquitto)
        BROKER="local"
        break
        ;;
      2|hivemq)
        BROKER="hivemq"
        break
        ;;
      *)
        echo "Pilihan tidak valid, ulangi lagi."
        ;;
    esac
  done
}

install_mosquitto() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y mosquitto mosquitto-clients
    return
  fi

  if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y mosquitto
    return
  fi

  if command -v yum >/dev/null 2>&1; then
    sudo yum install -y mosquitto
    return
  fi

  if command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm mosquitto
    return
  fi

  if command -v zypper >/dev/null 2>&1; then
    sudo zypper --non-interactive install mosquitto
    return
  fi

  echo "Package manager tidak dikenali. Install Mosquitto manual sesuai distro Anda."
}

start_mosquitto_service() {
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable --now mosquitto || true
    return
  fi

  if command -v service >/dev/null 2>&1; then
    sudo service mosquitto start || true
  fi
}

require_command "node" "Install Node.js LTS terlebih dahulu."
require_command "npm" "Install npm (biasanya sudah ikut Node.js)."

echo "Installer Vimo Server (Linux)"

if [[ -z "$BROKER" ]]; then
  choose_broker
fi

if [[ "$BROKER" != "local" && "$BROKER" != "hivemq" ]]; then
  echo "Error: broker harus local atau hivemq." >&2
  exit 1
fi

echo
echo "== Install dependency npm =="
npm install

if [[ "$BROKER" == "local" ]]; then
  echo
  read -r -p "Install Mosquitto broker sekarang? [Y/n]: " install_choice
  install_choice="${install_choice:-Y}"

  if [[ "${install_choice,,}" == "y" || "${install_choice,,}" == "yes" ]]; then
    echo "== Install Mosquitto =="
    install_mosquitto
    start_mosquitto_service
  else
    echo "Lewati install Mosquitto."
  fi
fi

echo
echo "== Generate root file .env =="
node ./scripts/setup-env.js --broker="$BROKER" --force

echo
echo "Setup selesai."
echo "Jalankan server:"
echo "  npm run start"

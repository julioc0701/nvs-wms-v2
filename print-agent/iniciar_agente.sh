#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export BACKEND_URL="${BACKEND_URL:-http://localhost:8003/api}"
export MACHINE_ID="${MACHINE_ID:-DEV_$(hostname)}"
export PRINTER_NAME="${PRINTER_NAME:-}"
export RECONNECT_BASE="${RECONNECT_BASE:-1}"
export RECONNECT_MAX="${RECONNECT_MAX:-10}"

echo "=========================================================="
echo " Agente Zebra NVS v3.0 | MODO DESENVOLVIMENTO macOS"
echo "----------------------------------------------------------"
echo " Backend   : $BACKEND_URL"
echo " Machine ID: $MACHINE_ID"
echo " Printer   : ${PRINTER_NAME:-auto/CUPS}"
echo "=========================================================="
echo

if [[ ! -x ".venv/bin/python" ]]; then
  echo "[ERRO] Ambiente virtual nao encontrado. Rode ./setup_print_agent.sh"
  exit 1
fi

exec ".venv/bin/python" agent.py

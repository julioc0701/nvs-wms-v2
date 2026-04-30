#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS Zebra Agent - Setup macOS ==="

find_python() {
  if command -v pyenv >/dev/null 2>&1; then
    local pyenv_python=""
    pyenv_python="$(pyenv which python 2>/dev/null || true)"
    if [[ -n "$pyenv_python" && -x "$pyenv_python" ]]; then
      printf '%s\n' "$pyenv_python"
      return 0
    fi
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

PYTHON_BOOTSTRAP="$(find_python || true)"
if [[ -z "$PYTHON_BOOTSTRAP" ]]; then
  echo "[ERRO] Python 3 nao encontrado."
  exit 1
fi

"$PYTHON_BOOTSTRAP" -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install "websockets>=12.0"

echo
echo "Setup concluido."
echo "Configure PRINTER_NAME se autodeteccao CUPS nao encontrar Zebra."
echo "Exemplo: PRINTER_NAME=Zebra_ZD421 ./iniciar_operacao.sh"

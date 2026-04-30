#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS·WMS - Setup Isolado (macOS) ==="

if [[ ! -f ".env.code" ]]; then
  echo "[ERRO] Arquivo .env.code nao encontrado."
  exit 1
fi

set -a
source <(grep -v '^[[:space:]]*#' ".env.code" | sed '/^[[:space:]]*$/d')
set +a

mkdir -p data

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

find_npm() {
  if command -v npm >/dev/null 2>&1; then
    command -v npm
    return 0
  fi

  if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    source "$HOME/.nvm/nvm.sh" >/dev/null 2>&1
    if command -v npm >/dev/null 2>&1; then
      command -v npm
      return 0
    fi
  fi

  local latest_npm=""
  latest_npm="$(find "$HOME/.nvm/versions/node" -path '*/bin/npm' 2>/dev/null | sort | tail -n 1 || true)"
  if [[ -n "$latest_npm" ]]; then
    printf '%s\n' "$latest_npm"
    return 0
  fi

  return 1
}

NPM_BIN="$(find_npm || true)"
if [[ -z "$NPM_BIN" ]]; then
  echo "[ERRO] npm nao encontrado. Instale Node.js."
  exit 1
fi

NODE_BIN_DIR="$(dirname "$NPM_BIN")"
export PATH="$NODE_BIN_DIR:$PATH"

echo
echo "[1/3] Criando ambiente virtual Python..."
"$PYTHON_BOOTSTRAP" -m venv .venv

echo
echo "[2/3] Instalando dependencias do backend..."
"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -r backend/requirements.txt

echo
echo "[3/3] Instalando dependencias do frontend..."
(cd frontend && "$NPM_BIN" install)
chmod -R u+rwX frontend/node_modules
find frontend/node_modules/.bin -type f -exec chmod u+rwx {} \;

echo
echo "Setup concluido."
echo "Frontend: http://localhost:${VITE_PORT:-5174}"
echo "Backend:  http://localhost:${FASTAPI_PORT:-8001}"
echo "DB:       ${DATABASE_URL:-sqlite:///../data/code-isolated.db}"
echo
echo "Proximo passo: rode ./start_isolado.sh"

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS·WMS - Start Isolado (macOS) ==="

if [[ ! -f ".env.code" ]]; then
  echo "[ERRO] Arquivo .env.code nao encontrado."
  exit 1
fi

set -a
source <(grep -v '^[[:space:]]*#' ".env.code" | sed '/^[[:space:]]*$/d')
set +a

export VITE_PORT="${VITE_PORT:-5174}"
export FASTAPI_PORT="${FASTAPI_PORT:-8001}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:$FASTAPI_PORT}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///../data/code-isolated.db}"
export FASTAPI_DB_PATH="${FASTAPI_DB_PATH:-../data/code-isolated.db}"

mkdir -p data .run

if [[ ! -d ".venv" ]]; then
  echo "[AVISO] Ambiente Python local .venv nao encontrado. O backend vai tentar usar o Python do sistema."
fi

if [[ -x "$HOME/.pyenv/bin/pyenv" ]]; then
  export PATH="$HOME/.pyenv/bin:$PATH"
  eval "$("$HOME/.pyenv/bin/pyenv" init -)" >/dev/null 2>&1 || true
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
  echo "[ERRO] npm nao encontrado."
  exit 1
fi

NODE_BIN_DIR="$(dirname "$NPM_BIN")"
export PATH="$NODE_BIN_DIR:$PATH"

if lsof -iTCP:"$FASTAPI_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRO] A porta $FASTAPI_PORT ja esta em uso."
  exit 1
fi

if lsof -iTCP:"$VITE_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRO] A porta $VITE_PORT ja esta em uso."
  exit 1
fi

BACKEND_LOG=".run/backend.log"
FRONTEND_LOG=".run/frontend.log"
BACKEND_PID_FILE=".run/backend.pid"
FRONTEND_PID_FILE=".run/frontend.pid"

echo
echo "Iniciando backend isolado..."
nohup "$ROOT_DIR/run_backend_isolado.sh" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

sleep 2

echo "Iniciando frontend isolado..."
nohup "$ROOT_DIR/run_frontend_isolado.sh" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

sleep 3

if command -v open >/dev/null 2>&1; then
  open "http://localhost:$VITE_PORT" >/dev/null 2>&1 || true
fi

echo
echo "Ambiente isolado rodando:"
echo "  Frontend: http://localhost:$VITE_PORT"
echo "  Backend:  http://localhost:$FASTAPI_PORT"
echo "  API docs: http://localhost:$FASTAPI_PORT/docs"
echo
echo "PIDs:"
echo "  Backend:  $BACKEND_PID"
echo "  Frontend: $FRONTEND_PID"
echo
echo "Logs:"
echo "  $ROOT_DIR/$BACKEND_LOG"
echo "  $ROOT_DIR/$FRONTEND_LOG"
echo
echo "Para parar: ./stop_isolado.sh"

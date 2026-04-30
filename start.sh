#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS - Start (macOS) ==="

export FASTAPI_PORT="${FASTAPI_PORT:-8003}"
export VITE_PORT="${VITE_PORT:-5176}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:$FASTAPI_PORT}"

mkdir -p .run

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

find_python() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
    return 0
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

if lsof -iTCP:"$FASTAPI_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRO] A porta $FASTAPI_PORT ja esta em uso."
  exit 1
fi

if lsof -iTCP:"$VITE_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRO] A porta $VITE_PORT ja esta em uso."
  exit 1
fi

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERRO] Python nao encontrado."
  exit 1
fi

NPM_BIN="$(find_npm || true)"
if [[ -z "$NPM_BIN" ]]; then
  echo "[ERRO] npm nao encontrado."
  exit 1
fi

NODE_BIN_DIR="$(dirname "$NPM_BIN")"
export PATH="$NODE_BIN_DIR:$PATH"

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "[ERRO] frontend/node_modules nao encontrado. Rode ./setup_isolado.sh ou instale as dependencias antes."
  exit 1
fi

if [[ ! -f "$ROOT_DIR/backend/main.py" ]]; then
  echo "[ERRO] backend/main.py nao encontrado."
  exit 1
fi

BACKEND_LOG=".run/start_backend.log"
FRONTEND_LOG=".run/start_frontend.log"
BACKEND_PID_FILE=".run/start_backend.pid"
FRONTEND_PID_FILE=".run/start_frontend.pid"

echo
echo "Starting backend..."
(
  cd "$ROOT_DIR/backend"
  exec "$PYTHON_BIN" -m uvicorn main:app --reload --host 0.0.0.0 --port "$FASTAPI_PORT"
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

sleep 2

echo "Starting frontend..."
(
  cd "$ROOT_DIR/frontend"
  exec "$NPM_BIN" run dev
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

sleep 3

echo "Opening browser..."
if command -v open >/dev/null 2>&1; then
  open "http://localhost:$VITE_PORT" >/dev/null 2>&1 || true
fi

echo
echo "Application running!"
echo "  Frontend: http://localhost:$VITE_PORT"
echo "  Backend:  http://localhost:$FASTAPI_PORT"
echo "  API docs: http://localhost:$FASTAPI_PORT/docs"
echo
echo "Logs:"
echo "  $ROOT_DIR/$BACKEND_LOG"
echo "  $ROOT_DIR/$FRONTEND_LOG"
echo
echo "Para parar no Mac: ./stop.sh"

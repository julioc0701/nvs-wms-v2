#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/frontend"

if [[ -f "$ROOT_DIR/.env.code" ]]; then
  set -a
  source <(grep -v '^[[:space:]]*#' "$ROOT_DIR/.env.code" | sed '/^[[:space:]]*$/d')
  set +a
fi

export VITE_PORT="${VITE_PORT:-5174}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:8001}"

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
  echo "[ERRO] npm nao encontrado. Instale Node.js antes de iniciar o frontend."
  exit 1
fi

NODE_BIN_DIR="$(dirname "$NPM_BIN")"
export PATH="$NODE_BIN_DIR:$PATH"

exec "$NPM_BIN" run dev -- --host 127.0.0.1 --port "$VITE_PORT"

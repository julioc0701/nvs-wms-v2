#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/backend"

if [[ -f "$ROOT_DIR/.env.code" ]]; then
  set -a
  # Load the isolated environment without forcing shell-specific syntax.
  source <(grep -v '^[[:space:]]*#' "$ROOT_DIR/.env.code" | sed '/^[[:space:]]*$/d')
  set +a
fi

mkdir -p "$ROOT_DIR/data"

export FASTAPI_PORT="${FASTAPI_PORT:-8001}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///../data/code-isolated.db}"
export FASTAPI_DB_PATH="${FASTAPI_DB_PATH:-../data/code-isolated.db}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v pyenv >/dev/null 2>&1; then
    PYENV_PYTHON="$(pyenv which python 2>/dev/null || true)"
    if [[ -n "$PYENV_PYTHON" && -x "$PYENV_PYTHON" ]]; then
      PYTHON_BIN="$PYENV_PYTHON"
    fi
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[ERRO] Python nao encontrado. Rode ./setup_isolado.sh ou instale Python 3."
    exit 1
  fi
fi

exec "$PYTHON_BIN" -m uvicorn main:app --reload --host 127.0.0.1 --port "$FASTAPI_PORT"

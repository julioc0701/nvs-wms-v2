#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS·WMS - Stop Isolado (macOS) ==="

if [[ -f ".env.code" ]]; then
  set -a
  source <(grep -v '^[[:space:]]*#' ".env.code" | sed '/^[[:space:]]*$/d')
  set +a
fi

stop_from_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file"
  fi
}

stop_from_pid_file ".run/backend.pid"
stop_from_pid_file ".run/frontend.pid"

if [[ -n "${FASTAPI_PORT:-}" ]]; then
  backend_pids="$(lsof -tiTCP:"$FASTAPI_PORT" -sTCP:LISTEN || true)"
  if [[ -n "$backend_pids" ]]; then
    kill $backend_pids >/dev/null 2>&1 || true
  fi
fi

if [[ -n "${VITE_PORT:-}" ]]; then
  frontend_pids="$(lsof -tiTCP:"$VITE_PORT" -sTCP:LISTEN || true)"
  if [[ -n "$frontend_pids" ]]; then
    kill $frontend_pids >/dev/null 2>&1 || true
  fi
fi

echo "Processos do ambiente isolado foram encerrados, se existiam."

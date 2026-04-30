#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== NVS - Stop (macOS) ==="

stop_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$label: sem PID salvo."
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"

  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "$label: parando PID $pid..."
    kill "$pid" >/dev/null 2>&1 || true
  else
    echo "$label: PID antigo/inativo ($pid)."
  fi

  rm -f "$pid_file"
}

stop_pid_file "Backend" ".run/start_backend.pid"
stop_pid_file "Frontend" ".run/start_frontend.pid"

echo "Stop concluido."

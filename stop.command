#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

clear
echo "=== NVS - Parar local no Mac ==="
echo

./stop.sh
STATUS=$?

echo
echo "Pressione ENTER para fechar."
read -r

exit "$STATUS"

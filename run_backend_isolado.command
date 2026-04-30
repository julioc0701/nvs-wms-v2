#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
clear
echo "=== NVS - Backend isolado Mac ==="
echo
./run_backend_isolado.sh
STATUS=$?
echo
echo "Pressione ENTER para fechar."
read -r
exit "$STATUS"

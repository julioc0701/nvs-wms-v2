#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
clear
echo "=== NVS - Iniciar isolado no Mac ==="
echo
./start_isolado.sh
STATUS=$?
echo
echo "Pressione ENTER para fechar."
read -r
exit "$STATUS"

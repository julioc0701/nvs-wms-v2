#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
clear
echo "=== NVS - Publicar producao no Mac ==="
echo
./publicar_producao.sh
STATUS=$?
echo
echo "Pressione ENTER para fechar."
read -r
exit "$STATUS"

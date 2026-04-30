#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
clear
echo "=== Print Agent - Iniciar operacao Mac ==="
echo
./iniciar_operacao.sh
STATUS=$?
echo
echo "Pressione ENTER para fechar."
read -r
exit "$STATUS"

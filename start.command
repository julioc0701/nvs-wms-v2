#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

clear
echo "=== NVS - Iniciar local no Mac ==="
echo

./start.sh
STATUS=$?

echo
if [[ "$STATUS" -eq 0 ]]; then
  echo "Start concluido. Pode usar o navegador."
else
  echo "Start falhou com codigo $STATUS."
  echo "Veja os logs em:"
  echo "  $SCRIPT_DIR/.run/start_backend.log"
  echo "  $SCRIPT_DIR/.run/start_frontend.log"
fi

echo
echo "Pode fechar esta janela quando quiser."
echo "Pressione ENTER para fechar."
read -r

exit "$STATUS"

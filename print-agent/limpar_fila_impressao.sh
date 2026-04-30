#!/usr/bin/env bash

set -euo pipefail

echo "======================================================"
echo " EMERGENCIA: LIMPAR FILA DE IMPRESSAO CUPS"
echo "======================================================"
echo
echo "Isto cancela jobs da impressora informada ou de todas as filas."
echo
read -r -p "Nome da impressora CUPS (vazio = todas): " printer
read -r -p "Confirmar limpeza da fila? [S/N]: " confirm
case "$confirm" in
  S|s) ;;
  *) echo "Operacao cancelada."; exit 0 ;;
esac

if [[ -n "$printer" ]]; then
  cancel -a "$printer" || true
else
  cancel -a || true
fi

echo "Fila CUPS limpa."

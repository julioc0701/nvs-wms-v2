#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "======================================================="
echo "      PUBLICACAO NVS-WMS v2 -> RAILWAY"
echo "======================================================="
echo
echo "Projeto  : virtuous-unity (Railway)"
echo "Repo     : github.com/julioc0701/nvs-wms-v2"
echo "Branch   : main"
echo "URL      : https://nvs-wms-v2-production.up.railway.app"
echo
echo "Este script vai:"
echo "  1. Rodar git add + commit"
echo "  2. Enviar para GitHub na branch main"
echo "  3. Railway inicia build automaticamente"
echo
read -r -p "> Voce testou localmente e quer PUBLICAR agora? [S/N]: " confirm
case "$confirm" in
  S|s) ;;
  *)
    echo "Publicacao cancelada."
    exit 0
    ;;
esac

echo
echo "[1/2] Salvando e versionando codigo..."
git add .
if ! git commit -m "deploy: publicar producao v2"; then
  echo "Nenhuma mudanca pendente para commitar. Seguindo com push."
fi

echo
echo "[2/2] Enviando para GitHub (branch main)..."
git push origin main

echo
echo "======================================================="
echo "PUBLICACAO INICIADA COM SUCESSO"
echo "Railway esta buildando nova versao."
echo "Railway: https://railway.com/project/d377de82-4ee6-42b7-8196-8f5f99915f4b"
echo "App:     https://nvs-wms-v2-production.up.railway.app"
echo "======================================================="

@echo off
title Agente Zebra Industrial NVS v3.0 — PRODUCAO
cd /d "%~dp0"

:: =====================================================================
::  CONFIGURACOES DE PRODUCAO (v2 — Railway)
:: =====================================================================
set BACKEND_URL=https://nvs-wms-v2-production.up.railway.app/api

:: Identificador unico desta maquina no armazem.
:: Troque para MAQUINA_2, MAQUINA_3, etc. se houver multiplas estacoes.
set MACHINE_ID=MAQUINA_1

:: Deixe em branco para auto-detectar a Zebra.
:: Ou informe o nome exato: set PRINTER_NAME=ZD421 (192.168.1.10)
set PRINTER_NAME=

:: Backoff de reconexao (segundos): base, maximo
set RECONNECT_BASE=2
set RECONNECT_MAX=60

echo ==========================================================
echo  Agente Zebra Industrial NVS v3.0  ^|  MODO PRODUCAO
echo  ----------------------------------------------------------
echo  Backend   : %BACKEND_URL%
echo  Machine ID: %MACHINE_ID%
echo ==========================================================
echo.

:: Verifica dependencias
python -c "import websockets" 2>nul
if errorlevel 1 (
    echo  [AVISO] Dependencia 'websockets' nao encontrada. Instalando...
    pip install "websockets>=12.0"
    echo.
)

python -c "import win32print" 2>nul
if errorlevel 1 (
    echo  [AVISO] Dependencia 'pywin32' nao encontrada. Instalando...
    pip install pywin32
    echo.
)

:: Prefere o executavel compilado; cai para Python se nao existir
if exist ZebraAgent-WP.exe (
    ZebraAgent-WP.exe
) else if exist dist\ZebraAgent-WP.exe (
    dist\ZebraAgent-WP.exe
) else (
    echo  [INFO] Executavel nao encontrado — usando Python diretamente.
    python agent.py
)

pause

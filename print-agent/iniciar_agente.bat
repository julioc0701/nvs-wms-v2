@echo off
title Agente Zebra NVS v3.0 — DESENVOLVIMENTO LOCAL
cd /d "%~dp0"

:: =====================================================================
::  CONFIGURACOES DE DESENVOLVIMENTO (backend local)
:: =====================================================================
set BACKEND_URL=http://localhost:8003/api
set MACHINE_ID=DEV_%COMPUTERNAME%
set PRINTER_NAME=
set RECONNECT_BASE=1
set RECONNECT_MAX=10

echo ==========================================================
echo  Agente Zebra NVS v3.0  ^|  MODO DESENVOLVIMENTO
echo  ----------------------------------------------------------
echo  Backend   : %BACKEND_URL%
echo  Machine ID: %MACHINE_ID%
echo  WS URL    : ws://localhost:8003/ws/zebra-agent/%MACHINE_ID%
echo ==========================================================
echo.

echo  Verificando dependencias...

python -c "import websockets" 2>nul
if errorlevel 1 (
    echo  [AVISO] Instalando websockets...
    pip install "websockets>=12.0"
)

python -c "import win32print" 2>nul
if errorlevel 1 (
    echo  [AVISO] Instalando pywin32...
    pip install pywin32
)

echo.
echo  Iniciando agente (Ctrl+C para parar)...
echo.

python agent.py
pause

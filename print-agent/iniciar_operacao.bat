@echo off
setlocal
title NVS Zebra Agent - OPERACAO
cd /d "%~dp0"

rem ==========================================================
rem  AGENTE DE OPERACAO
rem  ----------------------------------------------------------
rem  Este arquivo e para as maquinas do armazem.
rem  Nao requer Python, Node, pip ou npm.
rem  Requer apenas ZebraAgent-WP.exe nesta mesma pasta.
rem ==========================================================

set BACKEND_URL=https://nvs-wms-v2-production.up.railway.app/api

rem IMPORTANTE:
rem Cada maquina precisa ter um MACHINE_ID unico.
rem Exemplos: MAQUINA_1, MAQUINA_2, MAQUINA_3, MAQUINA_4
set MACHINE_ID=MAQUINA_1

rem Opcional: coloque o nome exato da impressora para evitar autodeteccao errada.
rem Exemplo: set PRINTER_NAME=ZDesigner ZD421-203dpi ZPL
set PRINTER_NAME=

set RECONNECT_BASE=2
set RECONNECT_MAX=60

echo ==========================================================
echo  NVS Zebra Agent - OPERACAO
echo  ----------------------------------------------------------
echo  Backend   : %BACKEND_URL%
echo  Machine ID: %MACHINE_ID%
echo  Printer   : %PRINTER_NAME%
echo ==========================================================
echo.

if not exist ZebraAgent-WP.exe (
    echo [ERRO] ZebraAgent-WP.exe nao encontrado nesta pasta.
    echo Use o pacote gerado em print-agent\release.
    pause
    exit /b 1
)

ZebraAgent-WP.exe

echo.
echo Agente encerrado.
pause
endlocal

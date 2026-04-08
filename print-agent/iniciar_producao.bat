@echo off
title Agente Industrial Zebra NVS v2.0
cd /d "%~dp0"

:: ---------------------------------------------------------------------
:: CONFIGURAÇÕES DE PRODUÇÃO (RAILWAY)
:: ---------------------------------------------------------------------
set ENABLE_POLLING=1
set BACKEND_URL=https://nvs-producao.up.railway.app/api
set POLL_INTERVAL=2

echo ==========================================================
echo  Iniciando AGENTE ZEBRA INDUSTRIAL V2.0 (MODO PRODUCAO)
echo  ------------------------------------------------------
echo  Conectando em: %BACKEND_URL%
echo  Intervalo    : %POLL_INTERVAL%s
echo ==========================================================
echo.

if exist ZEBRA_INDUSTRIAL_V2.exe (
    ZEBRA_INDUSTRIAL_V2.exe
) else (
    echo [ERRO CRITICO] Nao encontrei ZEBRA_INDUSTRIAL_V2.exe.
    echo Certifique-se de que o executavel esta na mesma pasta deste arquivo.
    pause
)

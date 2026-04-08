@echo off
title Agente de Impressao Zebra — NVS
cd /d "%~dp0"

:: =====================================================================
:: URL do backend — altere conforme o ambiente:
:: Local:   http://localhost:8001/api   (padrao)
:: Railway: https://SEU-APP.up.railway.app/api
:: =====================================================================
if not defined BACKEND_URL (
    set BACKEND_URL=http://localhost:8001/api
)

echo.
echo  Backend URL  : %BACKEND_URL%
echo.

echo  Verificando dependencias...
python -c "import win32print" 2>nul
if errorlevel 1 (
    echo  [AVISO] pywin32 nao encontrado. Instalando...
    pip install pywin32
    echo.
)

echo  Iniciando agente...
python agent.py
pause

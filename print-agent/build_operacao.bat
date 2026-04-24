@echo off
setlocal
title Build - ZebraAgent-WP OPERACAO
cd /d "%~dp0"

echo ==========================================================
echo  BUILD DO AGENTE DE OPERACAO
echo  ----------------------------------------------------------
echo  Este script e para a maquina de desenvolvimento.
echo  Requer Python + PyInstaller.
echo  A maquina da operacao NAO precisa de Python.
echo ==========================================================
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [ERRO] PyInstaller nao encontrado.
    echo Instale na maquina de desenvolvimento com:
    echo   pip install pyinstaller pywin32 websockets
    pause
    exit /b 1
)

if not exist ZebraAgent-WP.spec (
    echo [ERRO] ZebraAgent-WP.spec nao encontrado nesta pasta.
    pause
    exit /b 1
)

echo [1/3] Compilando executavel...
pyinstaller ZebraAgent-WP.spec --clean
if errorlevel 1 (
    echo.
    echo [ERRO] Compilacao falhou.
    pause
    exit /b 1
)

echo.
echo [2/3] Montando pacote de operacao...
if not exist release mkdir release
copy /Y dist\ZebraAgent-WP.exe release\ZebraAgent-WP.exe >nul
copy /Y iniciar_operacao.bat release\iniciar_operacao.bat >nul
copy /Y README_OPERACAO.md release\README_OPERACAO.md >nul

echo.
echo [3/3] Pacote pronto:
echo   print-agent\release\
echo.
echo Copie a pasta release para C:\NVS-ZebraAgent em cada maquina da operacao.
echo Em cada maquina, edite MACHINE_ID no iniciar_operacao.bat.
echo.
pause
endlocal

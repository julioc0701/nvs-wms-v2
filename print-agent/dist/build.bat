@echo off
title Build — ZebraAgent-WP.exe
cd /d "%~dp0"

echo.
echo  Compilando ZebraAgent-WP.exe...
echo.

pyinstaller ZebraAgent-WP.spec --clean

if errorlevel 1 (
    echo.
    echo  [ERRO] Compilacao falhou. Veja as mensagens acima.
    pause
    exit /b 1
)

copy /Y dist\ZebraAgent-WP.exe ZebraAgent-WP.exe

echo.
echo  [OK] ZebraAgent-WP.exe atualizado com sucesso.
echo.
pause

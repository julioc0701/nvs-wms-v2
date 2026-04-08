@echo off
setlocal
title Limpador de Fila de Impressao - NVS

echo ======================================================
echo    REINICIANDO SPOOLER E LIMPANDO FILA DE IMPRESSAO
echo ======================================================
echo.

:: Verifica privilégios de Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Este script precisa ser executado como ADMINISTRADOR.
    echo.
    echo Por favor, clique com o botao direito no arquivo e selecione
    echo "Executar como administrador".
    echo.
    pause
    exit /b 1
)

echo [1/4] Parando o servico de Spooler (Forçado)...
net stop spooler /y >nul 2>&1
taskkill /F /IM spoolsv.exe /T >nul 2>&1
echo.

echo [2/4] Limpando arquivos temporarios da fila...
del /Q /F /S "%systemroot%\System32\Spool\Printers\*.*" >nul 2>&1
echo.

echo [3/4] Reiniciando o servico de Spooler...
net start spooler
echo.

echo [4/4] Tentando colocar impressoras ONLINE via PowerShell...
powershell -Command "Get-Printer | Where-Object {$_.JobCount -gt 0 -or $_.PrinterStatus -eq 'Offline'} | Set-Printer -IsOffline $false"
echo.

echo ======================================================
echo    PROCESSO CONCLUIDO!
echo    1. Fila limpa.
echo    2. Servico reiniciado.
echo    3. Impressora forçada para ONLINE.
echo.
echo DICA: Se ainda aparecer 'Offline' na janela, clique em
echo 'Impressora' e desmarque 'Usar Impressora Offline'.
echo ======================================================
echo.
pause

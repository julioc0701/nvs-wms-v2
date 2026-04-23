@echo off
title Carga DB: v1 → v2
echo =======================================================
echo         CARGA DO BANCO DE DADOS  v1 → v2
echo =======================================================
echo.
echo  Este script:
echo   1. Baixa o banco de producao da v1 (eloquent-flexibility)
echo   2. Envia para a v2 (nvs-wms-v2-production.up.railway.app)
echo.
echo  Precisa de: curl instalado no PATH
echo.

set V1_URL=https://nvs-producao.up.railway.app
set V2_URL=https://nvs-wms-v2-production.up.railway.app

echo  v1: %V1_URL%
echo  v2: %V2_URL%
echo.
set /p SECRET_V1="> DOWNLOAD_SECRET da v1 (eloquent-flexibility): "
set /p SECRET_V2="> DOWNLOAD_SECRET da v2 (virtuous-unity): "

if "%SECRET_V1%"=="" (echo ERRO: SECRET da v1 nao informado. & pause & exit /b 1)
if "%SECRET_V2%"=="" (echo ERRO: SECRET da v2 nao informado. & pause & exit /b 1)

echo.
echo [1/3] Baixando banco de dados da v1...
curl -f -o v1_backup.db "%V1_URL%/api/admin/download-db?secret=%SECRET_V1%"
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha ao baixar DB da v1.
    echo Verifique a URL e o DOWNLOAD_SECRET.
    pause
    exit /b 1
)

echo.
echo [2/3] Verificando arquivo baixado...
for %%A in (v1_backup.db) do set SIZE=%%~zA
echo Tamanho: %SIZE% bytes
if %SIZE% LSS 10000 (
    echo AVISO: Arquivo muito pequeno — pode estar corrompido!
    set /p ok="> Continuar mesmo assim? [S/N]: "
    if /I NOT "%ok%"=="S" (del v1_backup.db & pause & exit /b 1)
)

echo.
echo [3/3] Enviando para a v2...
curl -f -X POST "%V2_URL%/api/admin/restore-db?secret=%SECRET_V2%" ^
     -F "file=@v1_backup.db"
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha ao enviar DB para v2.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo  CARGA CONCLUIDA!
echo  Arquivo local: v1_backup.db (pode apagar depois)
echo.
echo  IMPORTANTE: Reinicie o servico v2 no Railway para
echo  que as conexoes SQLAlchemy apontem para o novo DB.
echo  (Settings → Restart no painel)
echo =======================================================
del v1_backup.db
pause

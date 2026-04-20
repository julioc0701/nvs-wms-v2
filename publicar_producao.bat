@echo off
title Publicar NVS-WMS v2 em Producao (Railway)
echo =======================================================
echo       PUBLICACAO NVS-WMS v2  →  RAILWAY
echo =======================================================
echo.
echo  Projeto  : virtuous-unity (Railway)
echo  Repo     : github.com/julioc0701/nvs-wms-v2
echo  Branch   : main  (Railway faz deploy automatico ao receber push)
echo  URL      : https://nvs-wms-v2-production.up.railway.app
echo.
echo  Passos que este script fara:
echo   1. Salvar todas as mudancas pendentes (git add + commit)
echo   2. Enviar para o GitHub (branch main)
echo   3. Railway detecta o push e inicia o novo build automaticamente
echo.

set /p confirm="> Voce testou localmente e quer PUBLICAR as mudancas agora? [S/N]: "
if /I NOT "%confirm%"=="S" (
    echo.
    echo Publicacao cancelada.
    pause
    exit /b
)

echo.
echo [1/2] Salvando e versionando o codigo...
git add .
git commit -m "deploy: publicar producao v2"
if %errorlevel% neq 0 (
    echo Nenhuma mudanca pendente para commitar — OK, seguindo com push.
)

echo.
echo [2/2] Enviando para o GitHub (branch main)...
git push origin main
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Falha no git push. Verifique sua conexao e credenciais.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo  PUBLICACAO INICIADA COM SUCESSO!
echo.
echo  Railway esta buildando a nova versao agora.
echo  Acompanhe em: https://railway.com/project/d377de82-4ee6-42b7-8196-8f5f99915f4b
echo.
echo  URL da aplicacao:
echo  https://nvs-wms-v2-production.up.railway.app
echo =======================================================
pause

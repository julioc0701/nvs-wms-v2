@echo off
title Publicar em Producao (Railway)
echo =======================================================
echo          SISTEMA DE PUBLICACAO PARA PRODUCAO
echo =======================================================
echo.
echo  Atençao: O seu servidor Railway esta configurado para 
echo  rodar APENAS o que for enviado para a branch 'nvs-production'.
echo.
echo  Passos que este script fara:
echo  1. Salvar qualquer mudanca pendente na sua branch atual (main).
echo  2. Enviar a sua branch atual para o GitHub (como backup).
echo  3. Pegar esse codigo aprovado e injetar na branch 'nvs-production'.
echo  4. Enviar a branch 'nvs-production' para a nuvem, O QUE VAI DISPARAR O NOVO BUILD NO RAILWAY.
echo.

set /p confirm="> Voce testou localmente e quer PUBLICAR as mudancas agora [S/N]? "
if /I NOT "%confirm%"=="S" (
    echo.
    echo Publicacao cancelada.
    pause
    exit /b
)

echo.
echo [1/4] Salvando o codigo atual...
git add .
git commit -m "Auto-save antes de publicar" 

echo.
echo [2/4] Atualizando backup da branch principal (main)...
git push origin main

echo.
echo [3/4] Preparando a branch de producao...
git checkout -B nvs-production 

echo.
echo [4/4] Enviando para o Railway (Isto inicia um novo Deploy!)...
git push origin nvs-production --force

echo.
echo Retornando para o ambiente de desenvolvimento (main)...
git checkout main

echo.
echo =======================================================
echo  PUBLICACAO CONCLUIDA COM SUCESSO!
echo  O Railway comecara a gerar a nova versao em instantes.
echo =======================================================
pause

@echo off
setlocal EnableDelayedExpansion

echo === NVS·WMS - Setup Isolado ===

if not exist ".env.code" (
  echo [ERRO] Arquivo .env.code nao encontrado.
  exit /b 1
)

echo.
echo [1/3] Carregando variaveis de ambiente isoladas...
for /f "usebackq tokens=1,* delims==" %%A in (".env.code") do (
  set "k=%%A"
  set "v=%%B"
  if not "!k!"=="" if not "!k:~0,1!"=="#" set "!k!=!v!"
)

if not exist "data" mkdir data

echo.
echo [2/3] Instalando dependencias backend...
cd backend
pip install -r requirements.txt
cd ..

echo.
echo [3/3] Instalando dependencias frontend...
cd frontend
npm install
cd ..

echo.
echo Setup concluido.
echo Frontend: http://localhost:%VITE_PORT%
echo Backend:  http://localhost:%FASTAPI_PORT%
echo DB:       %DATABASE_URL%
echo.
echo Proximo passo: rode start_isolado.bat

endlocal

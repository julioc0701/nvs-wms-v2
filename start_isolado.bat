@echo off
setlocal EnableDelayedExpansion

echo === NVS·WMS - Start Isolado ===

set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist "%ROOT%.env.code" (
  echo [ERRO] Arquivo .env.code nao encontrado.
  goto :fail
)

set "PY_EXE="
set "PY_KIND="
where python >nul 2>&1
if not errorlevel 1 (
  set "PY_EXE=python"
  set "PY_KIND=python"
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    set "PY_EXE=py"
    set "PY_KIND=py"
  ) else (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
      set "PY_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
      set "PY_KIND=path"
    )
  )
)

if "%PY_EXE%"=="" (
  echo [ERRO] Python nao encontrado no PATH.
  echo Instale/ative Python ou valide se o launcher "py" existe.
  echo Testes:
  echo   python --version
  echo   py -3 --version
  goto :fail
)

set "NPM_EXE="
where npm >nul 2>&1
if not errorlevel 1 (
  set "NPM_EXE=npm"
) else (
  if exist "%ProgramFiles%\nodejs\npm.cmd" (
    set "NPM_EXE=%ProgramFiles%\nodejs\npm.cmd"
  ) else (
    if exist "%ProgramFiles(x86)%\nodejs\npm.cmd" (
      set "NPM_EXE=%ProgramFiles(x86)%\nodejs\npm.cmd"
    )
  )
)

if "%NPM_EXE%"=="" (
  echo [ERRO] NPM nao encontrado no PATH.
  echo Verifique instalacao do Node.js.
  echo Testes:
  echo   npm -v
  echo   "%ProgramFiles%\nodejs\npm.cmd" -v
  goto :fail
)

if not exist "%ROOT%data" mkdir "%ROOT%data"

for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT%.env.code") do (
  set "k=%%A"
  set "v=%%B"
  if not "!k!"=="" if not "!k:~0,1!"=="#" set "!k!=!v!"
)

if "%VITE_PORT%"=="" set VITE_PORT=5174
if "%FASTAPI_PORT%"=="" set FASTAPI_PORT=8001
if "%VITE_API_URL%"=="" set VITE_API_URL=http://localhost:%FASTAPI_PORT%
if "%DATABASE_URL%"=="" set DATABASE_URL=sqlite:///../data/code-isolated.db
if "%FASTAPI_DB_PATH%"=="" set FASTAPI_DB_PATH=../data/code-isolated.db

rem Force safe isolated DB path when old env still points to ./data under backend
if /i "%DATABASE_URL%"=="sqlite:///./data/code-isolated.db" set DATABASE_URL=sqlite:///../data/code-isolated.db
if /i "%FASTAPI_DB_PATH%"=="./data/code-isolated.db" set FASTAPI_DB_PATH=../data/code-isolated.db

set "BACKEND_RUNNER=%ROOT%run_backend_isolado.cmd"
set "FRONTEND_RUNNER=%ROOT%run_frontend_isolado.cmd"

(
  echo @echo off
  echo cd /d "%ROOT%backend"
  echo if not exist "..\data" mkdir "..\data"
  echo set DATABASE_URL=%DATABASE_URL%
  echo set FASTAPI_DB_PATH=%FASTAPI_DB_PATH%
  if /i "%PY_KIND%"=="python" (
    echo python -m uvicorn main:app --reload --host 127.0.0.1 --port %FASTAPI_PORT%
  ) else if /i "%PY_KIND%"=="py" (
    echo py -3 -m uvicorn main:app --reload --host 127.0.0.1 --port %FASTAPI_PORT%
  ) else (
    echo "%PY_EXE%" -m uvicorn main:app --reload --host 127.0.0.1 --port %FASTAPI_PORT%
  )
) > "%BACKEND_RUNNER%"

(
  echo @echo off
  echo cd /d "%ROOT%frontend"
  echo set VITE_PORT=%VITE_PORT%
  echo set VITE_API_URL=%VITE_API_URL%
  echo call "%NPM_EXE%" run dev -- --host 127.0.0.1 --port %VITE_PORT%
) > "%FRONTEND_RUNNER%"

echo.
echo Iniciando backend isolado...
start "NVS Backend Isolado" cmd /k ""%BACKEND_RUNNER%""

timeout /t 2 /nobreak > nul

echo Iniciando frontend isolado...
start "NVS Frontend Isolado" cmd /k ""%FRONTEND_RUNNER%""

timeout /t 3 /nobreak > nul

echo Abrindo navegador...
start http://localhost:%VITE_PORT%

echo.
echo Ambiente isolado rodando:
echo   Frontend: http://localhost:%VITE_PORT%
echo   Backend:  http://localhost:%FASTAPI_PORT%
echo   API docs: http://localhost:%FASTAPI_PORT%/docs
echo.
echo Para parar: stop_isolado.bat

endlocal
exit /b 0

:fail
echo.
echo [FALHA] O start_isolado encontrou um erro e foi interrompido.
echo [DICA] Rode este arquivo pelo CMD para ver detalhes:
echo        cd /d "%ROOT%"
echo        start_isolado.bat
echo.
pause
endlocal
exit /b 1

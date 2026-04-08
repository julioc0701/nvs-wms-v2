@echo off
setlocal

echo === NVS·WMS - Stop Isolado ===

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174') do taskkill /F /PID %%a >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do taskkill /F /PID %%a >nul 2>nul

echo Processos nas portas 5174 e 8001 foram encerrados (se existiam).

endlocal

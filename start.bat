@echo off
echo === NVS ===

echo Starting backend...
start "Backend" cmd /k "cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8003"

timeout /t 2 /nobreak > nul

echo Starting frontend...
start "Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 /nobreak > nul

echo Opening browser...
start http://localhost:5176

echo.
echo Application running!
echo   Frontend: http://localhost:5176
echo   Backend:  http://localhost:8003
echo   API docs: http://localhost:8003/docs

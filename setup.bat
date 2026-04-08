@echo off
echo === NVS - Setup ===

echo.
echo [1/3] Installing Python dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo.
echo [2/3] Installing Node dependencies...
cd frontend
npm install
cd ..

echo.
echo [3/3] Done! Run start.bat to launch the application.
pause

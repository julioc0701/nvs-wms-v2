@echo off
cd /d "C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2\frontend"
set VITE_PORT=5174
set VITE_API_URL=http://localhost:8001
call "C:\Program Files\nodejs\npm.cmd" run dev -- --host 127.0.0.1 --port 5174

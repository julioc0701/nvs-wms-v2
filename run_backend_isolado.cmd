@echo off
cd /d "C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2\backend"
if not exist "..\data" mkdir "..\data"
set DATABASE_URL=sqlite:///../data/code-isolated.db
set FASTAPI_DB_PATH=../data/code-isolated.db
"C:\Users\julio\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8001

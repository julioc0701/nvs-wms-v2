import os
import time
# NVS-WMS v2
from fastapi import FastAPI, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from logger import get_logger

# Carrega variáveis do .env (Token do Tiny, etc)
load_dotenv()

log = get_logger("api")

from database import init_db, get_db
from routers import sessions, operators, labels, printers, seed, barcodes, print_jobs, stats, tiny, ai, zebra_ws
from models import Operator
from services.sync_engine import recover_stale_runs, start_local_scheduler, stop_local_scheduler

app = FastAPI(title="NVS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logger(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        log.error(f"UNHANDLED {request.method} {request.url.path} — {exc}", exc_info=True)
        raise
    if response.status_code >= 400:
        log.warning(f"{request.method} {request.url.path} → {response.status_code}")
    return response

app.include_router(operators.router, prefix="/api/operators", tags=["operators"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(labels.router, prefix="/api/labels", tags=["labels"])
app.include_router(printers.router, prefix="/api/printers", tags=["printers"])
app.include_router(seed.router, prefix="/api/test", tags=["seed"])
app.include_router(barcodes.router, prefix="/api/barcodes", tags=["barcodes"])
app.include_router(print_jobs.router, prefix="/api/print-jobs", tags=["print-jobs"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(tiny.router, prefix="/api/tiny", tags=["tiny"])
app.include_router(ai.router, prefix="/api/v2/ai", tags=["ai"])
app.include_router(zebra_ws.router)   # WebSocket sem prefixo: /ws/zebra-agent/{id} + /api/zebra/agent-status

DEFAULT_OPERATORS = ["Master", "Julio", "Cris", "Rafael", "Luidi", "Weligton", "Cristofer", "Renan"]


@app.on_event("startup")
async def on_startup():
    init_db()
    recovered_runs = recover_stale_runs()
    db = next(get_db())
    try:
        for name in DEFAULT_OPERATORS:
            if not db.query(Operator).filter(Operator.name == name).first():
                db.add(Operator(name=name, pin_code="1234"))
        db.commit()
    finally:
        db.close()
    if recovered_runs:
        print(f"[SYNC] {recovered_runs} execucoes running antigas foram encerradas no startup.")
    if os.getenv("ENABLE_LOCAL_SYNC_SCHEDULER", "false").strip().lower() in {"1", "true", "yes"}:
        start_local_scheduler(os.getenv("TINY_API_TOKEN", ""))


@app.on_event("shutdown")
async def on_shutdown():
    # Sinalizamos para as engrenagens de fundo da Olist abortarem para não prenderem o servidor.
    import routers.tiny as tiny
    tiny.IS_SHUTTING_DOWN = True
    await stop_local_scheduler()
    print("[SISTEMA] Sinal de Desligamento enviado para a Máquina do Tempo.")


@app.get("/api/health")
def health(db = Depends(get_db)):
    try:
        from models import OrderOperational, TinyOrderItem, TinyOrderSync
        orders = db.query(TinyOrderSync).count()
        items = db.query(TinyOrderItem).count()
        canonical = db.query(OrderOperational).count()
    except Exception as e:
        orders, items, canonical = -1, -1, -1
    return {"status": "ok", "version": "2.2-pendente", "db_orders_synced": orders, "db_items_synced": items, "db_orders_canonical": canonical}


@app.get("/api/v2/sync")
def sync_v2():
    """Nuclear option for data sync via GET."""
    import os, shutil
    from database import DATABASE_URL
    db_path = DATABASE_URL.replace("sqlite:////", "/").replace("sqlite:///", "")
    db_path = os.path.abspath(db_path)
    repo_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "warehouse_v3_local.db"))
    if not os.path.exists(repo_db):
        return {"error": f"Repo DB not found at {repo_db}"}
    shutil.copy2(repo_db, db_path)
    return {"status": "success", "message": "DATA COPIED! Restarting app recommended."}


@app.get("/api/admin/seed-now")
def force_seed_endpoint():
    """Force the copy of the repo DB to the volume path."""
    import os
    import shutil
    from database import DATABASE_URL
    
    if "/data/" not in DATABASE_URL:
        return {"status": "error", "message": "Not in production volume environment"}
        
    if DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")
    else:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        
    db_path = os.path.abspath(db_path)
    # Inside container, backend file is in the same dir as this main.py or one level up
    repo_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "warehouse_v3_local.db"))
    
    if not os.path.exists(repo_db):
        return {"status": "error", "message": f"Source DB not found at {repo_db}"}
        
    try:
        shutil.copy2(repo_db, db_path)
        return {"status": "ok", "message": "SUCCESS! File copied. Please restart your service now."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/admin/download-db")
def download_db(secret: str = ""):
    """Download the live production database. Protected by DOWNLOAD_SECRET env var."""
    import os
    from fastapi.responses import FileResponse
    from database import DATABASE_URL

    expected = os.getenv("DOWNLOAD_SECRET", "")
    if not expected or secret != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Unauthorized — set DOWNLOAD_SECRET env var and pass ?secret=")

    if DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")
    else:
        db_path = DATABASE_URL.replace("sqlite:///", "")

    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        return {"status": "error", "message": f"DB not found at {db_path}"}

    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename="warehouse_v3_local_prod.db"
    )



@app.post("/api/admin/restore-db")
async def restore_db(secret: str = "", file: UploadFile = File(...)):
    """Recebe um arquivo .db e substitui o banco de produção. Requer DOWNLOAD_SECRET."""
    import os, shutil
    from database import DATABASE_URL

    expected = os.getenv("DOWNLOAD_SECRET", "")
    if not expected or secret != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Unauthorized")

    if DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")
    else:
        db_path = DATABASE_URL.replace("sqlite:///", "")
    db_path = os.path.abspath(db_path)

    tmp_path = db_path + ".upload_tmp"
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        size = os.path.getsize(tmp_path)
        # Checkpoint e troca para journal_mode=DELETE para eliminar WAL/SHM
        try:
            import sqlite3 as _sq
            _c = _sq.connect(tmp_path)
            _c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _c.execute("PRAGMA journal_mode=DELETE")
            _c.close()
        except Exception:
            pass
        # Remove WAL/SHM antigos do destino (incompatíveis com o novo DB)
        for _ext in ['-wal', '-shm']:
            _old = db_path + _ext
            if os.path.exists(_old):
                os.remove(_old)
        # Atomic replace
        shutil.move(tmp_path, db_path)
        return {"status": "ok", "message": f"DB restored ({size} bytes). Restart service to reload connections."}
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"status": "error", "message": str(e)}


@app.get("/api/admin/logs")
def get_logs(n: int = 200):
    """Retorna as últimas N linhas do log para diagnóstico remoto."""
    from logger import LOG_FILE
    if not os.path.exists(LOG_FILE):
        return {"lines": [], "file": LOG_FILE}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return {"lines": lines[-n:], "total": len(lines), "file": LOG_FILE}

@app.post("/api/admin/frontend-log")
async def receive_frontend_log(request: Request):
    """Recebe erros e eventos do frontend e grava no log central."""
    front_log = get_logger("frontend")
    try:
        body = await request.json()
        level = body.get("level", "error").upper()
        msg = body.get("message", "")
        ctx = body.get("context", {})
        getattr(front_log, level.lower(), front_log.error)(f"[FRONT] {msg} | ctx={ctx}")
    except Exception as e:
        front_log.error(f"[FRONT] falha ao parsear log: {e}")
    return {"ok": True}


# Serve React frontend (production build)
# This must come AFTER all /api routes
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

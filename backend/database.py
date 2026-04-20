import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# In production (Railway), set DATABASE_URL=sqlite:////data/warehouse_v3_local.db
# and mount a persistent volume at /data
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./warehouse_v3_local.db")
print(f"--- DATABASE DEBUG: URL is '{DATABASE_URL}' ---")

# ── Production Data Safety: Seed only if there's NO real data ─────────────────
if "/data/" in DATABASE_URL:
    if DATABASE_URL.startswith("sqlite:////"):
        db_path = DATABASE_URL.replace("sqlite:////", "/")
    else:
        db_path = DATABASE_URL.replace("sqlite:///", "")

    db_path = os.path.abspath(db_path)
    print(f"--- DATABASE DEBUG: Final target path is '{db_path}' ---")

    raw_force_seed = str(os.getenv("FORCE_SEED", "false")).strip().lower()
    force_seed = raw_force_seed in ("true", "1", "yes")
    print(f"--- DATABASE DEBUG: FORCE_SEED={force_seed} ---")

    # ── CRITICAL: Detect if production DB already has real operational data ───
    # We query the DB directly. If barcodes OR sessions exist, data is LIVE.
    # Only seed (overwrite) if DB is truly empty or FORCE_SEED is explicitly set.
    has_real_data = False
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"--- DATABASE DEBUG: Target file exists. Size: {size} bytes ---")
        if size > 10000:  # File exists and is non-trivial in size
            try:
                conn_check = sqlite3.connect(db_path)
                cur = conn_check.cursor()
                # Check for operational data
                cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='barcodes'")
                has_barcodes_table = cur.fetchone()[0] > 0
                if has_barcodes_table:
                    barcode_count = cur.execute("SELECT COUNT(*) FROM barcodes").fetchone()[0]
                    session_count = cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                    has_real_data = barcode_count > 0 or session_count > 0
                    print(f"--- DATABASE DEBUG: Found {barcode_count} barcodes, {session_count} sessions ---")
                conn_check.close()
            except Exception as e:
                print(f"--- DATABASE DEBUG: Could not inspect existing DB: {e} ---")
    else:
        print("--- DATABASE DEBUG: Target file does NOT exist. Will seed. ---")

    should_seed = not os.path.exists(db_path) or (force_seed and not has_real_data) or force_seed == "force_override"

    # ── SAFETY GATE: Never overwrite if real data exists (unless FORCE_SEED=true) ──
    if has_real_data and not force_seed:
        print(f"--- DATABASE SAFETY: Production data detected. Skipping seed to protect data. ---")
        should_seed = False
    elif has_real_data and force_seed:
        print(f"--- DATABASE WARNING: FORCE_SEED=true with LIVE DATA. Proceeding with overwrite. ---")
        should_seed = True

    if should_seed:
        import shutil
        current_dir = os.path.dirname(__file__)
        seed_path = os.path.abspath(os.path.join(current_dir, "warehouse_v3_local.db"))
        print(f"--- DATABASE DEBUG: Looking for seed source at '{seed_path}' ---")
        
        if os.path.exists(seed_path):
            try:
                print(f"--- SEED: Copying repo DB ({os.path.getsize(seed_path)} bytes) to volume ({db_path}) ---")
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                shutil.copy2(seed_path, db_path)
                print(f"--- SEED DONE: Success! Size: {os.path.getsize(db_path)} bytes ---")
            except Exception as e:
                print(f"--- SEED ERROR: Failed to copy: {e} ---")
        else:
             print(f"--- SEED ERROR: Source '{seed_path}' not found in bundle! ---")
    else:
        print(f"--- DATABASE DEBUG: Data exists ({os.path.getsize(db_path)} bytes). skipping seed. ---")

from sqlalchemy import event

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DEBUG: Check table counts immediately on startup
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        # Check if tables exist first
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='operators'")).fetchone()
        if res:
            op_count = conn.execute(text("SELECT COUNT(*) FROM operators")).scalar()
            sess_count = conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar()
            sku_count = conn.execute(text("SELECT COUNT(*) FROM barcodes")).scalar()
            print(f"--- DATA VERIFICATION ---")
            print(f"--- Total Operators: {op_count} ---")
            print(f"--- Total Sessions: {sess_count} ---")
            print(f"--- Total Barcodes: {sku_count} ---")
            print(f"-------------------------")
        else:
            print("--- DATA VERIFICATION: Tables not found yet! ---")
except Exception as e:
    print(f"--- DATA VERIFICATION ERROR: {e} ---")


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import Operator, Session, PickingItem, Barcode, Label, ScanEvent, Printer, PrintJob, TinyOrderSync, AgentMemory, AgentRun, OrderOperational, SyncRun, TinyPickingList, TinyPickingListItem, Shortage, TinySeparationStatus, TinySeparationItemCache  # noqa
    Base.metadata.create_all(bind=engine)

    # Lightweight column migrations (SQLite doesn't support DROP COLUMN but ADD is fine)
    from sqlalchemy import text, inspect as sa_inspect
    insp = sa_inspect(engine)
    with engine.connect() as conn:
        cols = [c["name"] for c in insp.get_columns("barcodes")]
        if "description" not in cols:
            conn.execute(text("ALTER TABLE barcodes ADD COLUMN description VARCHAR(500)"))
            conn.commit()

        op_cols = [c["name"] for c in insp.get_columns("operators")]
        if "pin_code" not in op_cols:
            conn.execute(text("ALTER TABLE operators ADD COLUMN pin_code VARCHAR(20) NOT NULL DEFAULT '1234'"))
            conn.commit()

        picking_cols = [c["name"] for c in insp.get_columns("picking_items")]
        if "ml_code" not in picking_cols:
            conn.execute(text("ALTER TABLE picking_items ADD COLUMN ml_code VARCHAR(100)"))
            conn.commit()
        if "labels_printed" not in picking_cols:
            conn.execute(text("ALTER TABLE picking_items ADD COLUMN labels_printed BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()

        # Fix UNIQUE constraint on barcode since SQLite doesn't support DROP CONSTRAINT directly
        tbl_sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='barcodes'")).scalar()
        idx_sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='barcodes' AND sql LIKE '%UNIQUE%'")).scalar()
        
        needs_migration = False
        if tbl_sql and "UNIQUE (barcode)" in tbl_sql:
            needs_migration = True
        if idx_sql:
            needs_migration = True
            
        if needs_migration:
            print("--- DATABASE MIGRATION: Removing UNIQUE constraint from barcodes ---")
            conn.execute(text("""
            CREATE TABLE barcodes_tmp (
                id INTEGER NOT NULL PRIMARY KEY,
                barcode VARCHAR(200) NOT NULL,
                sku VARCHAR(100) NOT NULL,
                description VARCHAR(500),
                is_primary BOOLEAN NOT NULL,
                added_by INTEGER,
                added_at DATETIME NOT NULL,
                FOREIGN KEY(added_by) REFERENCES operators (id)
            )
            """))
            conn.execute(text("INSERT INTO barcodes_tmp SELECT id, barcode, sku, description, is_primary, added_by, added_at FROM barcodes"))
            conn.execute(text("DROP TABLE barcodes"))
            conn.execute(text("ALTER TABLE barcodes_tmp RENAME TO barcodes"))
            conn.commit()
            print("--- DATABASE MIGRATION: UNIQUE constraint removed successfully ---")

        # ── BATCH SUPPORT MIGRATION ───────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS batches (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                full_date  DATE NOT NULL,
                seq        INTEGER NOT NULL DEFAULT 1,
                name       VARCHAR(100) NOT NULL,
                status     VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL
            )
        """))
        conn.commit()

        batch_cols = [c["name"] for c in insp.get_columns("batches")]
        if "marketplace" not in batch_cols:
            conn.execute(text("ALTER TABLE batches ADD COLUMN marketplace VARCHAR(20) NOT NULL DEFAULT 'ml'"))
            conn.commit()
            print("--- DATABASE MIGRATION: marketplace added to batches ---")

        sess_cols = [c["name"] for c in insp.get_columns("sessions")]
        if "batch_id" not in sess_cols:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN batch_id INTEGER REFERENCES batches(id)"))
            conn.commit()
            print("--- DATABASE MIGRATION: batch_id added to sessions ---")

        if "marketplace" not in sess_cols:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN marketplace VARCHAR(20) NOT NULL DEFAULT 'ml'"))
            conn.commit()
            print("--- DATABASE MIGRATION: marketplace added to sessions ---")

        sync_run_cols = [c["name"] for c in insp.get_columns("sync_runs")] if "sync_runs" in insp.get_table_names() else []
        if "updated_at" not in sync_run_cols:
            conn.execute(text("ALTER TABLE sync_runs ADD COLUMN updated_at DATETIME"))
            conn.execute(text("UPDATE sync_runs SET updated_at = COALESCE(finished_at, started_at)"))
            conn.commit()
            print("--- DATABASE MIGRATION: updated_at added to sync_runs ---")

        # ── PICKING LIST SUPPORT MIGRATION ────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_picking_lists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       VARCHAR(200) NOT NULL,
                status     VARCHAR(20) NOT NULL DEFAULT 'pendente',
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_picking_list_items (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id               INTEGER NOT NULL REFERENCES tiny_picking_lists(id),
                sku                   VARCHAR(100) NOT NULL,
                description           TEXT,
                quantity              FLOAT NOT NULL,
                location              VARCHAR(100),
                source_separation_ids TEXT,
                picked_at             DATETIME
            )
        """))
        conn.commit()
        print("--- DATABASE MIGRATION: Picking Lists tables verified/created ---")

        try:
            items_cols = [c["name"] for c in insp.get_columns("tiny_picking_list_items")]
            if "picked_at" not in items_cols:
                conn.execute(text("ALTER TABLE tiny_picking_list_items ADD COLUMN picked_at DATETIME"))
                conn.commit()
            
            if "is_shortage" not in items_cols:
                conn.execute(text("ALTER TABLE tiny_picking_list_items ADD COLUMN is_shortage BOOLEAN DEFAULT 0"))
                conn.commit()
                print("--- DATABASE MIGRATION: is_shortage added to tiny_picking_list_items ---")

            if "qty_picked" not in items_cols:
                conn.execute(text("ALTER TABLE tiny_picking_list_items ADD COLUMN qty_picked FLOAT DEFAULT 0.0"))
                conn.commit()
                print("--- DATABASE MIGRATION: qty_picked added to tiny_picking_list_items ---")

            if "qty_shortage" not in items_cols:
                conn.execute(text("ALTER TABLE tiny_picking_list_items ADD COLUMN qty_shortage FLOAT DEFAULT 0.0"))
                conn.commit()
                print("--- DATABASE MIGRATION: qty_shortage added to tiny_picking_list_items ---")

            if "notes" not in items_cols:
                conn.execute(text("ALTER TABLE tiny_picking_list_items ADD COLUMN notes TEXT"))
                conn.commit()
                print("--- DATABASE MIGRATION: notes added to tiny_picking_list_items ---")
            
            # MIGRATION PARA SHORTAGES (OPERADOR)
            shortage_cols = [c["name"] for c in insp.get_columns("shortages")]
            if "operator_id" not in shortage_cols:
                conn.execute(text("ALTER TABLE shortages ADD COLUMN operator_id INTEGER REFERENCES operators(id)"))
                conn.commit()
                print("--- DATABASE MIGRATION: operator_id added to shortages ---")
        except Exception:
            pass

        # ── CACHE DE ITENS DE SEPARAÇÃO (warm-up em background, TTL 6h) ────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_separation_item_cache (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                separation_id VARCHAR(50) NOT NULL,
                sku           VARCHAR(100) NOT NULL,
                description   TEXT,
                quantity      FLOAT NOT NULL,
                location      VARCHAR(100),
                cached_at     DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sep_cache_sep_id ON tiny_separation_item_cache (separation_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sep_cache_cached_at ON tiny_separation_item_cache (cached_at)"))
        conn.commit()
        print("--- DATABASE MIGRATION: tiny_separation_item_cache table verified/created ---")

        # ── STATUS LOCAL DE SEPARAÇÕES (Tiny é somente-leitura, nunca escrevemos de volta) ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_separation_statuses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                separation_id VARCHAR(50) NOT NULL UNIQUE,
                status        VARCHAR(30) NOT NULL DEFAULT 'em_separacao',
                list_id       INTEGER REFERENCES tiny_picking_lists(id),
                created_at    DATETIME NOT NULL
            )
        """))
        conn.commit()
        print("--- DATABASE MIGRATION: tiny_separation_statuses table verified/created ---")

        # ── RENOMEAR LISTAS SEM SEQUÊNCIA (L{N} - DD/MM/YYYY HH:MM) ─────────────
        import re as _re
        rows = conn.execute(text("SELECT id, name, created_at FROM tiny_picking_lists ORDER BY created_at ASC")).fetchall()
        seq = 1
        for row in rows:
            list_id, name, created_at = row
            # Extrai data/hora do nome antigo, seja qual for o formato
            date_part = _re.sub(r'^(Lista\s*|L\d+\s*-\s*)', '', name).strip()
            new_name = f"L{seq} - {date_part}" if date_part else f"L{seq} - {created_at}"
            conn.execute(text("UPDATE tiny_picking_lists SET name = :n WHERE id = :id"), {"n": new_name, "id": list_id})
            seq += 1
        conn.commit()
        if rows:
            print(f"--- DATABASE MIGRATION: {len(rows)} picking list(s) renomeadas com sequencia L{{N}} ---")

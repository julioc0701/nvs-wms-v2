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
    # Always ensure the target directory exists (critical when no Railway volume yet)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
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
                # DB malformado — apaga para recomeçar limpo
                try:
                    conn_check.close()
                except Exception:
                    pass
                try:
                    os.remove(db_path)
                    for _ext in ['-wal', '-shm']:
                        _f = db_path + _ext
                        if os.path.exists(_f):
                            os.remove(_f)
                    print(f"--- DATABASE DEBUG: DB malformado removido. Iniciando fresh. ---")
                except Exception as del_e:
                    print(f"--- DATABASE DEBUG: Falha ao remover DB malformado: {del_e} ---")
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
    from models import Operator, Session, PickingItem, Barcode, Label, ScanEvent, Printer, PrintJob, TinyOrderSync, AgentMemory, AgentRun, OrderOperational, SyncRun, TinyPickingList, TinyPickingListItem, Shortage, TinySeparationStatus, TinySeparationItemCache, TinySeparationHeader, TinyErpSendLog, AutoSeparationState, MercadoLivreFullPlan, Boleto, BoletoBeneficiario, LancamentoCategoria  # noqa
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

        if "lifecycle" not in batch_cols:
            conn.execute(text("ALTER TABLE batches ADD COLUMN lifecycle VARCHAR(20) NOT NULL DEFAULT 'pendente'"))
            conn.commit()
            # Backfill inteligente para lotes existentes:
            # Se algum item já foi bipado em qualquer sessão do batch → 'em_andamento'
            conn.execute(text("""
                UPDATE batches
                SET lifecycle = 'em_andamento'
                WHERE id IN (
                    SELECT DISTINCT s.batch_id
                    FROM sessions s
                    INNER JOIN picking_items p ON p.session_id = s.id
                    WHERE s.batch_id IS NOT NULL AND p.qty_picked > 0
                )
            """))
            conn.commit()
            print("--- DATABASE MIGRATION: lifecycle added to batches (backfilled em_andamento for active batches) ---")

        sess_cols = [c["name"] for c in insp.get_columns("sessions")]
        if "batch_id" not in sess_cols:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN batch_id INTEGER REFERENCES batches(id)"))
            conn.commit()
            print("--- DATABASE MIGRATION: batch_id added to sessions ---")

        if "marketplace" not in sess_cols:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN marketplace VARCHAR(20) NOT NULL DEFAULT 'ml'"))
            conn.commit()
            print("--- DATABASE MIGRATION: marketplace added to sessions ---")

        print_job_cols = [c["name"] for c in insp.get_columns("print_jobs")] if "print_jobs" in insp.get_table_names() else []
        print_job_migrations = {
            "claimed_by": "ALTER TABLE print_jobs ADD COLUMN claimed_by VARCHAR(100)",
            "claimed_at": "ALTER TABLE print_jobs ADD COLUMN claimed_at DATETIME",
            "started_at": "ALTER TABLE print_jobs ADD COLUMN started_at DATETIME",
            "job_token": "ALTER TABLE print_jobs ADD COLUMN job_token VARCHAR(100)",
            "agent_version": "ALTER TABLE print_jobs ADD COLUMN agent_version VARCHAR(50)",
            "zpl_hash": "ALTER TABLE print_jobs ADD COLUMN zpl_hash VARCHAR(64)",
            "zpl_block_count": "ALTER TABLE print_jobs ADD COLUMN zpl_block_count INTEGER",
        }
        for col_name, ddl in print_job_migrations.items():
            if col_name not in print_job_cols:
                conn.execute(text(ddl))
                conn.commit()
                print(f"--- DATABASE MIGRATION: {col_name} added to print_jobs ---")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_print_jobs_claimed_by ON print_jobs (claimed_by)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_print_jobs_job_token ON print_jobs (job_token)"))
        conn.commit()

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

            # MIGRATION: source column em tiny_picking_lists (auto | manual)
            tpl_cols = [c["name"] for c in insp.get_columns("tiny_picking_lists")]
            if "source" not in tpl_cols:
                conn.execute(text("ALTER TABLE tiny_picking_lists ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual'"))
                conn.commit()
                print("--- DATABASE MIGRATION: source added to tiny_picking_lists ---")

            # MIGRATION: marketplace column em tiny_picking_lists (ml | shopee | null)
            tpl_cols = [c["name"] for c in insp.get_columns("tiny_picking_lists")]
            if "marketplace" not in tpl_cols:
                conn.execute(text("ALTER TABLE tiny_picking_lists ADD COLUMN marketplace VARCHAR(20)"))
                conn.commit()
                print("--- DATABASE MIGRATION: marketplace added to tiny_picking_lists ---")

            # MIGRATION PARA SHORTAGES (OPERADOR)
            shortage_cols = [c["name"] for c in insp.get_columns("shortages")]
            if "operator_id" not in shortage_cols:
                conn.execute(text("ALTER TABLE shortages ADD COLUMN operator_id INTEGER REFERENCES operators(id)"))
                conn.commit()
                print("--- DATABASE MIGRATION: operator_id added to shortages ---")

            if "status" not in shortage_cols:
                conn.execute(text("ALTER TABLE shortages ADD COLUMN status VARCHAR(20) DEFAULT 'pendente'"))
                conn.commit()
                print("--- DATABASE MIGRATION: status added to shortages ---")

            if "marketplace" not in shortage_cols:
                conn.execute(text("ALTER TABLE shortages ADD COLUMN marketplace VARCHAR(20)"))
                conn.commit()
                print("--- DATABASE MIGRATION: marketplace added to shortages ---")
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

        # MIGRATION: colunas de sincronização do marcador "SemEstoque" no Tiny
        status_cols = [c["name"] for c in insp.get_columns("tiny_separation_statuses")]
        if "marker_status" not in status_cols:
            conn.execute(text("ALTER TABLE tiny_separation_statuses ADD COLUMN marker_status VARCHAR(20)"))
            conn.execute(text("ALTER TABLE tiny_separation_statuses ADD COLUMN marker_error TEXT"))
            conn.execute(text("ALTER TABLE tiny_separation_statuses ADD COLUMN marker_sent_at DATETIME"))
            conn.commit()
            print("--- DATABASE MIGRATION: marker_status/error/sent_at added to tiny_separation_statuses ---")

        # ── HEADERS DE EXIBIÇÃO DE SEPARAÇÕES (cache para abas em_separacao/separadas) ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_separation_headers (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                separation_id         VARCHAR(50) NOT NULL UNIQUE,
                numero                VARCHAR(50),
                destinatario          VARCHAR(255),
                numero_ec             VARCHAR(100),
                data_emissao          VARCHAR(30),
                prazo_maximo          VARCHAR(30),
                id_forma_envio        VARCHAR(50),
                forma_envio_descricao VARCHAR(100),
                numero_pedido         VARCHAR(50),
                updated_at            DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sep_headers_sep_id ON tiny_separation_headers (separation_id)"))
        conn.commit()
        print("--- DATABASE MIGRATION: tiny_separation_headers table verified/created ---")

        # MIGRATION: id_pedido em tiny_separation_headers (idOrigemVinc = TinyOrderSync.id, usado nos marcadores)
        header_cols = [c["name"] for c in insp.get_columns("tiny_separation_headers")]
        if "id_pedido" not in header_cols:
            conn.execute(text("ALTER TABLE tiny_separation_headers ADD COLUMN id_pedido VARCHAR(50)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sep_headers_id_pedido ON tiny_separation_headers (id_pedido)"))
            # Backfill best-effort: tenta match via numero_pedido ↔ tiny_orders_sync.numero
            conn.execute(text("""
                UPDATE tiny_separation_headers
                SET id_pedido = (
                    SELECT t.id FROM tiny_orders_sync t
                    WHERE t.numero = tiny_separation_headers.numero_pedido
                    LIMIT 1
                )
                WHERE id_pedido IS NULL AND numero_pedido IS NOT NULL AND numero_pedido != ''
            """))
            conn.commit()
            print("--- DATABASE MIGRATION: id_pedido added to tiny_separation_headers (backfill via numero) ---")

        # ── ERP SEND LOGS ─────────────────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tiny_erp_send_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                separation_id VARCHAR(50) NOT NULL,
                triggered_by  VARCHAR(20) NOT NULL,
                status        VARCHAR(20) NOT NULL,
                response_json TEXT,
                error_message TEXT,
                sent_at       DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_erp_logs_sep_id ON tiny_erp_send_logs (separation_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_erp_logs_sent_at ON tiny_erp_send_logs (sent_at)"))
        conn.commit()
        print("--- DATABASE MIGRATION: tiny_erp_send_logs table verified/created ---")

        # ── AUTO SEPARATION STATE (singleton para banner de falha + idempotência) ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auto_separation_state (
                id                    INTEGER PRIMARY KEY,
                last_run_at           DATETIME,
                last_status           VARCHAR(30) NOT NULL DEFAULT 'never_ran',
                consecutive_failures  INTEGER NOT NULL DEFAULT 0,
                last_error_msg        TEXT,
                last_summary          TEXT
            )
        """))
        # Garante linha inicial (id=1) — singleton
        conn.execute(text("""
            INSERT OR IGNORE INTO auto_separation_state (id, last_status, consecutive_failures)
            VALUES (1, 'never_ran', 0)
        """))
        conn.commit()
        print("--- DATABASE MIGRATION: auto_separation_state table + initial row verified ---")

        # ── ML FULL PLANNING LOG ─────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_full_plans (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ml_plan_id        VARCHAR(100),
                title             VARCHAR(200) NOT NULL,
                status            VARCHAR(30) NOT NULL DEFAULT 'created',
                execution_mode    VARCHAR(30) NOT NULL DEFAULT 'manual',
                filter_label      VARCHAR(100),
                products_count    INTEGER NOT NULL DEFAULT 0,
                total_units       INTEGER NOT NULL DEFAULT 0,
                created_by        VARCHAR(100),
                notes             TEXT,
                raw_payload_json  TEXT,
                created_at        DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_plans_created_at ON ml_full_plans (created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_plans_status ON ml_full_plans (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_plans_plan_id ON ml_full_plans (ml_plan_id)"))
        conn.commit()
        print("--- DATABASE MIGRATION: ml_full_plans table verified/created ---")

        # ── ML FULL PLANNING TASKS / AGENT STATE ────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_full_planning_tasks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                status           VARCHAR(30) NOT NULL DEFAULT 'pending',
                requested_by     VARCHAR(100),
                agent_id         VARCHAR(100),
                run_mode         VARCHAR(30) NOT NULL DEFAULT 'simulate',
                units_strategy   VARCHAR(30) NOT NULL DEFAULT 'formula',
                fixed_units      INTEGER,
                percentage       INTEGER NOT NULL DEFAULT 20,
                min_units        INTEGER NOT NULL DEFAULT 1,
                filter_label     VARCHAR(150),
                filters_json     TEXT,
                result_json      TEXT,
                error_message    TEXT,
                created_plan_id  VARCHAR(100),
                products_count   INTEGER NOT NULL DEFAULT 0,
                total_units      INTEGER NOT NULL DEFAULT 0,
                created_at       DATETIME NOT NULL,
                started_at       DATETIME,
                finished_at      DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_tasks_status ON ml_full_planning_tasks (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_tasks_created_at ON ml_full_planning_tasks (created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_full_tasks_agent ON ml_full_planning_tasks (agent_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_full_agent_state (
                id             INTEGER PRIMARY KEY,
                agent_id       VARCHAR(100) NOT NULL DEFAULT 'mac-local-julio',
                status         VARCHAR(30) NOT NULL DEFAULT 'offline',
                last_seen_at   DATETIME,
                last_message   TEXT
            )
        """))
        conn.execute(text("""
            INSERT OR IGNORE INTO ml_full_agent_state (id, agent_id, status)
            VALUES (1, 'mac-local-julio', 'offline')
        """))
        conn.commit()
        print("--- DATABASE MIGRATION: ml_full_planning_tasks + ml_full_agent_state verified ---")

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

        # ── LIMPEZA DE FALTAS FANTASMA (idempotente) ──────────────────────────
        # Bug histórico: Picking.jsx fazia dupla escrita (api.shortage + api.reportShortage),
        # gerando registro fantasma na tabela `shortages` sem marketplace, duplicando
        # PickingItem.shortage_qty já existente. Frontend foi corrigido — aqui limpamos
        # as duplicatas históricas. Critério: mesmo SKU + mesma sessão + mesma qty.
        # Faltas orgânicas e legítimas (sem match em PickingItem) NÃO são tocadas.
        try:
            res = conn.execute(text("""
                SELECT COUNT(*), COALESCE(SUM(s.quantity), 0)
                FROM shortages s
                INNER JOIN picking_items p
                  ON p.sku = s.sku
                  AND CAST(p.session_id AS TEXT) = s.list_id
                  AND p.shortage_qty = s.quantity
                WHERE s.category = 'full'
                  AND p.shortage_qty > 0
            """)).fetchone()
            dup_count, dup_units = (res[0] or 0), (res[1] or 0)
            if dup_count > 0:
                conn.execute(text("""
                    DELETE FROM shortages
                    WHERE category = 'full'
                      AND id IN (
                        SELECT s.id FROM shortages s
                        INNER JOIN picking_items p
                          ON p.sku = s.sku
                          AND CAST(p.session_id AS TEXT) = s.list_id
                          AND p.shortage_qty = s.quantity
                        WHERE s.category = 'full'
                          AND p.shortage_qty > 0
                      )
                """))
                conn.commit()
                print(f"--- LIMPEZA_FANTASMA: removidos {dup_count} registros, {int(dup_units)} unidades duplicadas ---")
            else:
                print("--- LIMPEZA_FANTASMA: nenhuma duplicata encontrada (skip) ---")
        except Exception as e:
            print(f"--- LIMPEZA_FANTASMA ERROR: {e} ---")

        # ── FINANCEIRO — BOLETOS A PAGAR ──────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS boleto_beneficiarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razao_social VARCHAR(200) NOT NULL,
                banco VARCHAR(3) NOT NULL,
                campo_livre_prefix VARCHAR(6) NOT NULL,
                criado_em DATETIME NOT NULL,
                criado_por INTEGER REFERENCES operators(id)
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_benef_banco_prefix
            ON boleto_beneficiarios(banco, campo_livre_prefix)
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS boletos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_barras VARCHAR(44) NOT NULL,
                linha_digitavel VARCHAR(47) NOT NULL,
                banco_emissor VARCHAR(3) NOT NULL,
                valor FLOAT NOT NULL,
                vencimento DATE NOT NULL,
                beneficiario_id INTEGER REFERENCES boleto_beneficiarios(id),
                beneficiario_texto VARCHAR(200),
                observacao TEXT,
                foto_path VARCHAR(300),
                status VARCHAR(20) NOT NULL DEFAULT 'registrado',
                capturado_por INTEGER NOT NULL REFERENCES operators(id),
                capturado_em DATETIME NOT NULL,
                pago_em DATETIME,
                pago_por INTEGER REFERENCES operators(id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_boletos_status ON boletos(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_boletos_vencimento ON boletos(vencimento)"))
        # UNIQUE partial no codigo_barras: só checa unicidade se o valor não for NULL.
        # Lançamentos manuais (PIX, despesa) ficam sem código e não são afetados.
        # Recria o índice se existir como UNIQUE não-partial (legado).
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_boletos_codigo_unique"))
            conn.execute(text("DROP INDEX IF EXISTS idx_boletos_codigo"))
        except Exception:
            pass
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_boletos_codigo_unique "
            "ON boletos(codigo_barras) WHERE codigo_barras IS NOT NULL"
        ))
        conn.commit()

        # ── Migrações pra extensão de lançamentos (categoria, descricao, chave_pix) ──
        boleto_cols = [c["name"] for c in insp.get_columns("boletos")]
        if "categoria_id" not in boleto_cols:
            conn.execute(text("ALTER TABLE boletos ADD COLUMN categoria_id INTEGER REFERENCES lancamento_categorias(id)"))
        if "descricao" not in boleto_cols:
            conn.execute(text("ALTER TABLE boletos ADD COLUMN descricao TEXT"))
        if "chave_pix" not in boleto_cols:
            conn.execute(text("ALTER TABLE boletos ADD COLUMN chave_pix VARCHAR(200)"))
        conn.commit()

        # ── Categorias de lançamento ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS lancamento_categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(30),
                ordem INTEGER NOT NULL DEFAULT 0,
                ativa BOOLEAN NOT NULL DEFAULT 1,
                criada_em DATETIME NOT NULL,
                criada_por INTEGER REFERENCES operators(id)
            )
        """))
        conn.commit()

        # Pré-seed das categorias padrão se a tabela estiver vazia
        existe = conn.execute(text("SELECT COUNT(*) FROM lancamento_categorias")).scalar()
        if existe == 0:
            categorias_seed = [
                ("Boleto", "file-text", 1),
                ("PIX Fornecedor", "zap", 2),
                ("PIX Funcionário", "user", 3),
                ("Taxa", "receipt", 4),
                ("Reembolso", "rotate-ccw", 5),
                ("Água", "droplet", 6),
                ("Luz", "lightbulb", 7),
                ("Internet", "wifi", 8),
                ("Aluguel", "home", 9),
                ("Multa", "alert-triangle", 10),
                ("Outros", "more-horizontal", 99),
            ]
            for nome, icon, ordem in categorias_seed:
                conn.execute(
                    text(
                        "INSERT INTO lancamento_categorias (nome, icon, ordem, ativa, criada_em) "
                        "VALUES (:n, :i, :o, 1, :c)"
                    ),
                    {"n": nome, "i": icon, "o": ordem, "c": __import__('datetime').datetime.utcnow().isoformat()},
                )
            conn.commit()
            print(f"--- LANCAMENTO_CATEGORIAS: {len(categorias_seed)} categorias padrão inseridas ---")

        # Backfill: marca boletos antigos sem categoria como "Boleto" (id=1 após seed)
        try:
            boleto_cat_id = conn.execute(
                text("SELECT id FROM lancamento_categorias WHERE nome = 'Boleto' LIMIT 1")
            ).scalar()
            if boleto_cat_id:
                conn.execute(
                    text("UPDATE boletos SET categoria_id = :cid WHERE categoria_id IS NULL AND codigo_barras IS NOT NULL"),
                    {"cid": boleto_cat_id},
                )
                conn.commit()
        except Exception:
            pass
        conn.commit()

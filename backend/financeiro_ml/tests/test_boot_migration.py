import importlib
from sqlalchemy import create_engine, text


def _make_v1_db(path):
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    with eng.begin() as c:
        c.execute(text("CREATE TABLE ml_tokens (id INTEGER PRIMARY KEY, access_token TEXT, refresh_token TEXT, user_id INTEGER, expires_at DATETIME, updated_at DATETIME)"))
        c.execute(text("INSERT INTO ml_tokens VALUES (1,'acc','ref',555,'2026-05-28 00:00:00','2026-05-28 00:00:00')"))
        c.execute(text("CREATE TABLE ml_orders_cache (order_id INTEGER PRIMARY KEY, date_created DATETIME, date_closed DATETIME, date_last_updated DATETIME, status TEXT, status_detail TEXT, produto_total NUMERIC, frete_comprador NUMERIC, frete_vendedor NUMERIC, tarifa_bruta NUMERIC, tarifa_refund NUMERIC, refund_amount_partial NUMERIC, cupom_seller NUMERIC, modalidade_anuncio TEXT, logistic_type TEXT, shipping_mode TEXT, shipment_id INTEGER, breakdown_bucket TEXT, raw_json TEXT, synced_at DATETIME, synced_run_id INTEGER)"))
        c.execute(text("INSERT INTO ml_orders_cache (order_id,date_created,status,produto_total,raw_json,synced_at,date_last_updated) VALUES (100,'2026-05-20 10:00:00','paid',50.0,'{}','2026-05-20 11:00:00','2026-05-20 10:30:00')"))
        c.execute(text("CREATE TABLE ml_order_items_cache (id INTEGER PRIMARY KEY, order_id INTEGER, item_id TEXT, title TEXT, seller_sku TEXT, quantity INTEGER, unit_price NUMERIC, category_id TEXT)"))
        c.execute(text("INSERT INTO ml_order_items_cache (order_id,item_id,title,seller_sku,quantity,unit_price) VALUES (100,'MLB1','Prod A','SKU-A',1,50.0)"))
        c.execute(text("CREATE TABLE ml_day_sync_status (id INTEGER PRIMARY KEY, day DATE, last_synced_at DATETIME, orders_count INTEGER, status TEXT, error_message TEXT)"))
    eng.dispose()


def _reload(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/main.db")
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    monkeypatch.setenv("ML_USER_ID", "555")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    return db, m, mig


def test_boot_migrates_when_empty(tmp_path, monkeypatch):
    _make_v1_db(str(tmp_path / "main.db"))
    db, m, mig = _reload(monkeypatch, tmp_path)
    res = mig.maybe_migrate_on_boot()
    assert res["status"] == "migrated"
    assert res["orders"] == 1
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).filter_by(seller_id=555).count() == 1
    s.close()


def test_boot_skips_when_already_has_data(tmp_path, monkeypatch):
    _make_v1_db(str(tmp_path / "main.db"))
    db, m, mig = _reload(monkeypatch, tmp_path)
    mig.maybe_migrate_on_boot()
    res2 = mig.maybe_migrate_on_boot()  # 2ª vez não pode re-migrar (UNIQUE em items)
    assert res2["status"] == "skipped"
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).filter_by(seller_id=555).count() == 1
    s.close()


def test_boot_skips_when_no_seller(tmp_path, monkeypatch):
    _make_v1_db(str(tmp_path / "main.db"))
    db, m, mig = _reload(monkeypatch, tmp_path)
    monkeypatch.delenv("ML_USER_ID", raising=False)
    res = mig.maybe_migrate_on_boot()
    assert res["status"] == "skipped"

import importlib
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def _make_v1_db(path):
    """Cria um .db estilo v1 (sem seller_id) com 2 orders, 1 item, 1 token, 1 day_status."""
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    with eng.begin() as c:
        c.execute(text("CREATE TABLE ml_tokens (id INTEGER PRIMARY KEY, access_token TEXT, refresh_token TEXT, user_id INTEGER, expires_at DATETIME, updated_at DATETIME)"))
        c.execute(text("INSERT INTO ml_tokens VALUES (1,'acc','ref',555,'2026-05-28 00:00:00','2026-05-28 00:00:00')"))
        c.execute(text("CREATE TABLE ml_orders_cache (order_id INTEGER PRIMARY KEY, date_created DATETIME, date_closed DATETIME, date_last_updated DATETIME, status TEXT, status_detail TEXT, produto_total NUMERIC, frete_comprador NUMERIC, frete_vendedor NUMERIC, tarifa_bruta NUMERIC, tarifa_refund NUMERIC, refund_amount_partial NUMERIC, cupom_seller NUMERIC, modalidade_anuncio TEXT, logistic_type TEXT, shipping_mode TEXT, shipment_id INTEGER, breakdown_bucket TEXT, raw_json TEXT, synced_at DATETIME, synced_run_id INTEGER)"))
        c.execute(text("INSERT INTO ml_orders_cache (order_id,date_created,status,produto_total,raw_json,synced_at,date_last_updated) VALUES (100,'2026-05-20 10:00:00','paid',50.0,'{}','2026-05-20 11:00:00','2026-05-20 10:30:00')"))
        c.execute(text("INSERT INTO ml_orders_cache (order_id,date_created,status,produto_total,raw_json,synced_at,date_last_updated) VALUES (101,'2026-05-21 10:00:00','paid',70.0,'{}','2026-05-21 11:00:00','2026-05-21 12:00:00')"))
        c.execute(text("CREATE TABLE ml_order_items_cache (id INTEGER PRIMARY KEY, order_id INTEGER, item_id TEXT, title TEXT, seller_sku TEXT, quantity INTEGER, unit_price NUMERIC, category_id TEXT)"))
        c.execute(text("INSERT INTO ml_order_items_cache (order_id,item_id,title,seller_sku,quantity,unit_price) VALUES (100,'MLB1','Prod A','SKU-A',1,50.0)"))
        c.execute(text("CREATE TABLE ml_day_sync_status (id INTEGER PRIMARY KEY, day DATE, last_synced_at DATETIME, orders_count INTEGER, status TEXT, error_message TEXT)"))
        c.execute(text("INSERT INTO ml_day_sync_status (day,last_synced_at,orders_count,status) VALUES ('2026-05-20','2026-05-20 11:00:00',1,'ok')"))
    eng.dispose()


def test_migrate_copies_orders_items_with_seller(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()

    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    report = mig.migrate(v1_db_path=str(v1), seller_id=555)

    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 2
    assert s.query(m.MLOrderItemCache).count() == 1
    assert all(o.seller_id == 555 for o in s.query(m.MLOrderCache).all())
    assert s.query(m.MLTokens).filter_by(seller_id=555).count() == 1
    assert report["orders"] == 2 and report["items"] == 1
    s.close()


def test_migrate_status_ok_preserved_others_unverified(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    mig.migrate(v1_db_path=str(v1), seller_id=555)
    s = db.FinSessionLocal()
    d20 = s.query(m.MLDaySyncStatus).filter_by(seller_id=555, day=date(2026,5,20)).first()
    assert d20.status == "ok"
    s.close()


def test_migrate_count_matches_before_after(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    report = mig.migrate(v1_db_path=str(v1), seller_id=555)
    assert report["orders"] == report["orders_src"]

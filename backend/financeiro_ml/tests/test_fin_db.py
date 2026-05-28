import os
from sqlalchemy import text


def test_fin_engine_applies_pragmas(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import importlib
    import financeiro_ml.db as db
    importlib.reload(db)

    with db.fin_engine.connect() as conn:
        journal = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert journal.lower() == "wal"
    assert busy == 5000


def test_fin_session_factory_independent_from_main(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import importlib
    import financeiro_ml.db as db
    importlib.reload(db)
    from database import engine as main_engine
    assert str(db.fin_engine.url) != str(main_engine.url)
    s = db.FinSessionLocal()
    s.close()

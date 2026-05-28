import importlib
import pytest


@pytest.fixture
def fin_db(tmp_path, monkeypatch):
    """DB financeiro isolado, recriado por teste. Retorna o módulo db + models_v2."""
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    return db, m

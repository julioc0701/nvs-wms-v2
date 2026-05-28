"""Camada de banco ISOLADA do módulo financeiro_ml.

NÃO importar database.SessionLocal aqui. Engine própria apontando para
FINANCEIRO_ML_DATABASE_URL. PRAGMAs aplicados em CADA conexão (WAL +
busy_timeout=5000 + synchronous=NORMAL) — robô escreve, painel lê, sem
'database is locked'.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default local: arquivo próprio ao lado do principal. Railway: sqlite:////data/financeiro_ml.db
FINANCEIRO_ML_DATABASE_URL = os.getenv(
    "FINANCEIRO_ML_DATABASE_URL", "sqlite:///./financeiro_ml.db"
)

fin_engine = create_engine(
    FINANCEIRO_ML_DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(fin_engine, "connect")
def _set_fin_pragmas(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


FinSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=fin_engine)


class FinBase(DeclarativeBase):
    pass


def get_fin_db():
    db = FinSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_fin_db():
    """Cria todas as tabelas do schema v2 no banco isolado."""
    import financeiro_ml.models_v2  # noqa — registra modelos em FinBase.metadata
    FinBase.metadata.create_all(bind=fin_engine)

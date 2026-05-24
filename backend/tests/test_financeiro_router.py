"""Testes de integração das rotas /api/financeiro.

IMPORTANTE: usa um DB SQLite isolado por sessão de teste (arquivo temporário)
para NUNCA tocar no banco de desenvolvimento (`warehouse_v3_local.db`).
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient


# Código fictício válido (DV mod 11 = 5) usado nos testes
CODIGO_BOLETO_VALIDO = "237" + "9" + "5" + "3380" + "0000010005" + ("0" * 25)


@pytest.fixture(scope="session", autouse=True)
def _isolar_db():
    """Aponta DATABASE_URL para um arquivo temporário ANTES de qualquer import do app."""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    os.environ['DATABASE_URL'] = f'sqlite:///{tmp.name}'
    # Cria tabelas no DB temporário
    from database import init_db
    init_db()
    # Garante operador Master pra testes que precisam dele
    from database import get_db
    from models import Operator
    db = next(get_db())
    if not db.query(Operator).filter_by(name='Master').first():
        db.add(Operator(name='Master', pin_code='1234'))
        db.commit()
    db.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def db():
    from database import get_db
    return next(get_db())


@pytest.fixture
def operator_id(db):
    from models import Operator
    op = db.query(Operator).filter_by(name='Master').first()
    return op.id


@pytest.fixture(autouse=True)
def limpar_tabelas(db):
    """Limpa boletos + beneficiários antes de cada teste (DB já é isolado)."""
    from models import Boleto, BoletoBeneficiario
    db.query(Boleto).delete()
    db.query(BoletoBeneficiario).delete()
    db.commit()
    yield
    db.query(Boleto).delete()
    db.query(BoletoBeneficiario).delete()
    db.commit()


# ── /boletos/scan ─────────────────────────────────────────────────────────────


def test_scan_codigo_valido_retorna_dados_parseados(client):
    r = client.post("/api/financeiro/boletos/scan", json={"codigo_ou_linha": CODIGO_BOLETO_VALIDO})
    assert r.status_code == 200
    data = r.json()
    assert data["banco"] == "237"
    assert data["valor"] == 100.05
    assert data["dv_ok"] is True
    assert data["duplicata"] is None


def test_scan_codigo_invalido_retorna_400(client):
    r = client.post("/api/financeiro/boletos/scan", json={"codigo_ou_linha": "12345"})
    assert r.status_code == 400


def test_scan_arrecadacao_retorna_400(client):
    r = client.post("/api/financeiro/boletos/scan", json={"codigo_ou_linha": "8" + "0" * 43})
    assert r.status_code == 400


# ── POST /boletos ─────────────────────────────────────────────────────────────


def test_criar_boleto_basico_cria_beneficiario_novo(client, operator_id):
    body = {
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "Energisa Mato Grosso",
    }
    r = client.post("/api/financeiro/boletos", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["banco_emissor"] == "237"
    assert data["beneficiario_id"] is not None
    assert data["beneficiario_razao_social"] == "Energisa Mato Grosso"
    assert data["status"] == "registrado"


def test_criar_boleto_duplicado_retorna_409(client, operator_id):
    body = {
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "Energisa",
    }
    r1 = client.post("/api/financeiro/boletos", json=body)
    assert r1.status_code == 201
    r2 = client.post("/api/financeiro/boletos", json=body)
    assert r2.status_code == 409


def test_segundo_scan_sugere_beneficiario_existente(client, operator_id):
    # Primeiro registro cria o beneficiário
    body1 = {
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "Energisa",
    }
    client.post("/api/financeiro/boletos", json=body1)
    # Scan da mesma "empresa" (mesmo banco + mesmo prefix do campo livre) deve sugerir
    r = client.post("/api/financeiro/boletos/scan", json={"codigo_ou_linha": CODIGO_BOLETO_VALIDO})
    assert r.json()["beneficiario_sugerido"]["razao_social"] == "Energisa"


# ── GET /boletos ──────────────────────────────────────────────────────────────


def test_listar_aplica_filtro_status(client, operator_id):
    client.post("/api/financeiro/boletos", json={
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "X",
    })
    r = client.get("/api/financeiro/boletos?status=registrado")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["valor_total"] == 100.05
    assert all(b["status"] == "registrado" for b in data["boletos"])


# ── POST /boletos/{id}/pagar e /reabrir ───────────────────────────────────────


def test_marcar_pago_atualiza_status(client, operator_id):
    r1 = client.post("/api/financeiro/boletos", json={
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "X",
    })
    bid = r1.json()["id"]
    r2 = client.post(f"/api/financeiro/boletos/{bid}/pagar", json={"operator_id": operator_id})
    assert r2.status_code == 200
    assert r2.json()["status"] == "pago"
    assert r2.json()["pago_em"] is not None


def test_reabrir_volta_para_registrado(client, operator_id):
    r1 = client.post("/api/financeiro/boletos", json={
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "X",
    })
    bid = r1.json()["id"]
    client.post(f"/api/financeiro/boletos/{bid}/pagar", json={"operator_id": operator_id})
    r3 = client.post(f"/api/financeiro/boletos/{bid}/reabrir")
    assert r3.status_code == 200
    assert r3.json()["status"] == "registrado"
    assert r3.json()["pago_em"] is None


# ── DELETE /boletos/{id} ──────────────────────────────────────────────────────


def test_excluir_remove_boleto(client, operator_id):
    r1 = client.post("/api/financeiro/boletos", json={
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "X",
    })
    bid = r1.json()["id"]
    r2 = client.delete(f"/api/financeiro/boletos/{bid}")
    assert r2.status_code == 200
    r3 = client.get(f"/api/financeiro/boletos/{bid}")
    assert r3.status_code == 404


# ── GET /beneficiarios ────────────────────────────────────────────────────────


def test_beneficiarios_autocomplete_filtra_por_q(client, operator_id):
    client.post("/api/financeiro/boletos", json={
        "codigo_ou_linha": CODIGO_BOLETO_VALIDO,
        "operator_id": operator_id,
        "beneficiario_texto": "Energisa Mato Grosso",
    })
    r = client.get("/api/financeiro/beneficiarios?q=energ")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert "Energisa" in r.json()[0]["razao_social"]

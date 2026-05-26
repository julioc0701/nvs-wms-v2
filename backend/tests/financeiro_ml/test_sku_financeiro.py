import pytest
from decimal import Decimal
from database import SessionLocal, init_db
from models import SkuFinanceiro, Operator
from services.sku_financeiro_service import upsert_sku, list_skus, delete_sku


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        # Garante operator 1 existe
        if not s.query(Operator).filter_by(id=1).first():
            s.add(Operator(id=1, name="Test", badge="T", pin_code="1234"))
            s.commit()
        # Limpa skus pra isolar
        s.query(SkuFinanceiro).delete()
        s.commit()


def test_upsert_creates_new_sku():
    upsert_sku("SKU_NEW", custo_unit=Decimal("10.00"), imposto_pct=Decimal("8.50"), updated_by_id=1)
    with SessionLocal() as s:
        row = s.query(SkuFinanceiro).filter_by(sku="SKU_NEW").first()
        assert row is not None
        assert row.custo_unit == Decimal("10.00")


def test_upsert_updates_existing():
    upsert_sku("SKU_X", custo_unit=Decimal("5"), imposto_pct=Decimal("8"), updated_by_id=1)
    upsert_sku("SKU_X", custo_unit=Decimal("99"), imposto_pct=Decimal("10"), updated_by_id=1)
    with SessionLocal() as s:
        row = s.query(SkuFinanceiro).filter_by(sku="SKU_X").first()
        assert row.custo_unit == Decimal("99")
        assert row.imposto_pct == Decimal("10")


def test_list_skus_returns_dict():
    upsert_sku("SKU_A", custo_unit=Decimal("1"), imposto_pct=Decimal("9"), updated_by_id=1)
    upsert_sku("SKU_B", custo_unit=Decimal("2"), imposto_pct=Decimal("9"), updated_by_id=1)
    result = list_skus()
    assert "SKU_A" in result
    assert result["SKU_A"]["custo_unit"] == Decimal("1")


def test_delete_sku():
    upsert_sku("SKU_DEL", custo_unit=Decimal("1"), imposto_pct=Decimal("9"), updated_by_id=1)
    delete_sku("SKU_DEL")
    with SessionLocal() as s:
        assert s.query(SkuFinanceiro).filter_by(sku="SKU_DEL").first() is None

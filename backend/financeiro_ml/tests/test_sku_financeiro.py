import io
import pytest
from decimal import Decimal
from openpyxl import Workbook
from database import SessionLocal, init_db
from models import Operator
from financeiro_ml.models import SkuFinanceiro
from financeiro_ml.sku_service import upsert_sku, list_skus, delete_sku, import_excel


TEST_SKUS = ["SKU_NEW", "SKU_X", "SKU_A", "SKU_B", "SKU_DEL", "IMP_A", "IMP_B"]


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        # Garante operator 1 existe
        if not s.query(Operator).filter_by(id=1).first():
            s.add(Operator(id=1, name="Test", badge="T", pin_code="1234"))
            s.commit()
        # Limpa apenas dados criados por estes testes.
        s.query(SkuFinanceiro).filter(SkuFinanceiro.sku.in_(TEST_SKUS)).delete(synchronize_session=False)
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


def test_import_excel_creates_and_updates():
    # Prepara um xlsx fake com colunas sku, custo_unit, imposto_pct
    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "custo_unit", "imposto_pct"])
    ws.append(["IMP_A", 12.5, 8.0])
    ws.append(["IMP_B", 20.0, 9.5])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    result = import_excel(buf, updated_by_id=1)
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["errors"] == []

    # Reimport mesma planilha
    buf.seek(0)
    result2 = import_excel(buf, updated_by_id=1)
    assert result2["created"] == 0
    assert result2["updated"] == 2

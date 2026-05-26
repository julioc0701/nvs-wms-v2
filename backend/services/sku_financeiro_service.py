"""CRUD da tabela sku_financeiro + import Excel."""
from decimal import Decimal
from datetime import datetime

from database import SessionLocal
from models import SkuFinanceiro


def upsert_sku(sku: str, *, custo_unit: Decimal, imposto_pct: Decimal, updated_by_id: int) -> None:
    with SessionLocal() as session:
        row = session.query(SkuFinanceiro).filter_by(sku=sku).first()
        if row is None:
            row = SkuFinanceiro(sku=sku, custo_unit=custo_unit, imposto_pct=imposto_pct,
                                  updated_by=updated_by_id, updated_at=datetime.utcnow())
            session.add(row)
        else:
            row.custo_unit = custo_unit
            row.imposto_pct = imposto_pct
            row.updated_by = updated_by_id
            row.updated_at = datetime.utcnow()
        session.commit()


def list_skus(query: str | None = None) -> dict[str, dict]:
    with SessionLocal() as session:
        q = session.query(SkuFinanceiro)
        if query:
            q = q.filter(SkuFinanceiro.sku.like(f"%{query}%"))
        return {
            row.sku: {
                "custo_unit": row.custo_unit,
                "imposto_pct": row.imposto_pct,
                "updated_at": row.updated_at,
            }
            for row in q.all()
        }


def delete_sku(sku: str) -> bool:
    with SessionLocal() as session:
        row = session.query(SkuFinanceiro).filter_by(sku=sku).first()
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True

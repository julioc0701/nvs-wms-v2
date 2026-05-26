"""Rotas REST do Resumo Financeiro Mercado Livre.
Permissão: somente Master.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ============ Schemas ============

class FilterParams(BaseModel):
    data_inicio: date
    data_fim: date
    sku: str | None = None
    mlb: str | None = None
    status: Literal["aprovado", "cancelado", "todos"] = "todos"
    modalidade: Literal["premium", "classico", "gratis", "todos"] = "todos"
    tipo_frete: Literal["me1", "me2", "sem_me", "full", "flex", "outro", "todos"] = "todos"
    custo_imposto: Literal["sem_custo", "sem_imposto", "sem_custo_imposto", "todos"] = "todos"
    considerar_frete_comprador: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class SkuPayload(BaseModel):
    custo_unit: Decimal
    imposto_pct: Decimal


from fastapi import UploadFile, File
from services.sku_financeiro_service import upsert_sku, list_skus, delete_sku, import_excel


# TODO: substituir por dependência real de auth Master quando integrar com auth do projeto
def require_master() -> int:
    """Stub. Retorna operator_id 1. Trocar pela dependência real depois."""
    return 1


# ============ Rotas ============

@router.get("/skus")
async def get_skus(q: str | None = None, operator_id: int = Depends(require_master)):
    items = list_skus(q)
    return {
        "items": [
            {"sku": k, "custo_unit": str(v["custo_unit"]), "imposto_pct": str(v["imposto_pct"]),
             "updated_at": v["updated_at"].isoformat() if v.get("updated_at") else None}
            for k, v in items.items()
        ],
        "total": len(items),
    }


@router.put("/skus/{sku}")
async def put_sku(sku: str, payload: SkuPayload, operator_id: int = Depends(require_master)):
    upsert_sku(sku, custo_unit=payload.custo_unit, imposto_pct=payload.imposto_pct,
                updated_by_id=operator_id)
    return {"ok": True}


@router.delete("/skus/{sku}")
async def del_sku(sku: str, operator_id: int = Depends(require_master)):
    if not delete_sku(sku):
        raise HTTPException(status_code=404, detail="SKU não encontrado")
    return {"ok": True}


@router.post("/skus/import-excel")
async def import_skus_excel(file: UploadFile = File(...), operator_id: int = Depends(require_master)):
    content = await file.read()
    import io
    result = import_excel(io.BytesIO(content), updated_by_id=operator_id)
    return result


from datetime import datetime, time
from services.ml_sync import ensure_period_synced
from services.ml_aggregator import aggregate
from models import MLOrderCache, MLOrderItemCache, SkuFinanceiro
from sqlalchemy import and_


@router.post("/resumo")
async def get_resumo(params: FilterParams, operator_id: int = Depends(require_master)):
    sync_report = await ensure_period_synced(params.data_inicio, params.data_fim)

    from database import SessionLocal
    with SessionLocal() as session:
        date_from = datetime.combine(params.data_inicio, time.min)
        date_to = datetime.combine(params.data_fim, time.max)

        q = session.query(MLOrderCache).filter(
            and_(MLOrderCache.date_created >= date_from, MLOrderCache.date_created <= date_to)
        )
        if params.status == "aprovado":
            q = q.filter(MLOrderCache.status == "paid")
        elif params.status == "cancelado":
            q = q.filter(MLOrderCache.status == "cancelled")

        orders = [_row_to_dict_order(r) for r in q.all()]
        order_ids = [o["order_id"] for o in orders]

        items_q = session.query(MLOrderItemCache).filter(MLOrderItemCache.order_id.in_(order_ids))
        if params.sku:
            items_q = items_q.filter(MLOrderItemCache.seller_sku == params.sku)
        items = [_row_to_dict_item(r) for r in items_q.all()]

        skus_rows = session.query(SkuFinanceiro).all()
        sku_financeiro = {
            r.sku: {"custo_unit": Decimal(str(r.custo_unit)), "imposto_pct": Decimal(str(r.imposto_pct))}
            for r in skus_rows
        }

    result = aggregate(orders, items, sku_financeiro)

    # Paginação da tabela
    total = len(result["tabela"])
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    result["tabela"] = result["tabela"][start:end]
    result["pagination"] = {
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": (total + params.page_size - 1) // params.page_size,
    }
    result["sync_report"] = sync_report
    return _json_safe(result)


def _row_to_dict_order(r) -> dict:
    return {
        "order_id": r.order_id,
        "status": r.status,
        "date_created": r.date_created,
        "produto_total": Decimal(str(r.produto_total)),
        "frete_comprador": Decimal(str(r.frete_comprador)),
        "frete_vendedor": Decimal(str(r.frete_vendedor)),
        "tarifa_bruta": Decimal(str(r.tarifa_bruta)),
        "tarifa_refund": Decimal(str(r.tarifa_refund)),
        "refund_amount_partial": Decimal(str(r.refund_amount_partial)),
        "logistic_type": r.logistic_type,
        "shipping_mode": r.shipping_mode,
        "modalidade_anuncio": r.modalidade_anuncio,
        "breakdown_bucket": r.breakdown_bucket,
    }


def _row_to_dict_item(r) -> dict:
    return {
        "order_id": r.order_id,
        "item_id": r.item_id,
        "title": r.title,
        "seller_sku": r.seller_sku,
        "quantity": r.quantity,
        "unit_price": Decimal(str(r.unit_price)),
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@router.get("/health")
async def health():
    """Verifica que o módulo está vivo e que ml_tokens tem token."""
    from database import SessionLocal
    from models import MLTokens
    with SessionLocal() as session:
        token = session.query(MLTokens).first()
        return {
            "ok": True,
            "ml_configured": token is not None,
            "user_id": token.user_id if token else None,
        }

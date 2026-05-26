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

        # mlb: filtra por item_id LIKE
        if params.mlb:
            matching_order_ids = session.query(MLOrderItemCache.order_id).filter(
                MLOrderItemCache.item_id.like(f"%{params.mlb}%")
            ).distinct().subquery()
            q = q.filter(MLOrderCache.order_id.in_(matching_order_ids))

        # modalidade: gold_special/gold_pro/free
        modalidade_map = {"premium": "gold_special", "classico": "gold_pro", "gratis": "free"}
        if params.modalidade != "todos":
            q = q.filter(MLOrderCache.modalidade_anuncio == modalidade_map[params.modalidade])

        # tipo_frete: breakdown_bucket ou shipping_mode
        tipo_frete_map = {
            "me1": ("shipping_mode", "me1"),
            "me2": ("shipping_mode", "me2"),
            "sem_me": ("shipping_mode", "not_specified"),
            "full": ("breakdown_bucket", "full"),
            "flex": ("breakdown_bucket", "flex"),
            "outro": ("breakdown_bucket", "outros"),
        }
        if params.tipo_frete != "todos":
            field_name, value = tipo_frete_map[params.tipo_frete]
            q = q.filter(getattr(MLOrderCache, field_name) == value)

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

    # custo_imposto: filtra itens pós-fetch baseado em cadastro SKU
    if params.custo_imposto != "todos":
        def _is_missing_cost(item):
            sku = (item.get("seller_sku") or "").strip()
            if not sku or sku not in sku_financeiro:
                return True  # sem cadastro → custo=0 e imposto=0
            fin = sku_financeiro[sku]
            sem_custo = Decimal(str(fin["custo_unit"])) == 0
            sem_imp = Decimal(str(fin["imposto_pct"])) == 0
            if params.custo_imposto == "sem_custo":
                return sem_custo
            if params.custo_imposto == "sem_imposto":
                return sem_imp
            if params.custo_imposto == "sem_custo_imposto":
                return sem_custo and sem_imp
            return False
        items = [it for it in items if _is_missing_cost(it)]
        eligible_order_ids = {it["order_id"] for it in items}
        orders = [o for o in orders if o["order_id"] in eligible_order_ids]

    result = aggregate(orders, items, sku_financeiro,
                       considerar_frete_comprador=params.considerar_frete_comprador)

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


from fastapi.responses import StreamingResponse
import io
import csv
from openpyxl import Workbook


@router.post("/export")
async def export_resumo(params: FilterParams, formato: Literal["excel", "csv"] = "excel",
                         operator_id: int = Depends(require_master)):
    """Exporta a tabela do resumo (sem paginação) no formato pedido."""
    full = await get_resumo(FilterParams(**{**params.model_dump(), "page": 1, "page_size": 100000}),
                             operator_id=operator_id)
    rows = full["tabela"]

    if formato == "csv":
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")),
                                 media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=resumo.csv"})

    # Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    if rows:
        ws.append(list(rows[0].keys()))
        for r in rows:
            ws.append([r.get(k) for k in rows[0].keys()])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return StreamingResponse(bio,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=resumo.xlsx"})


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

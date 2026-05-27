"""Rotas REST do Resumo Financeiro Mercado Livre.
Permissão: somente Master.
"""
import logging
import time as time_module
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# Logger dedicado: aparece como [BUSCAR] no stderr/uvicorn
trace = logging.getLogger("financeiro_ml.trace")
trace.setLevel(logging.INFO)
if not trace.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[BUSCAR] %(message)s"))
    trace.addHandler(_h)
    trace.propagate = False


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
    margem: Literal["bom", "atencao", "critico", "todos"] = "todos"
    considerar_frete_comprador: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class SkuPayload(BaseModel):
    custo_unit: Decimal
    imposto_pct: Decimal


from fastapi import UploadFile, File
from database import get_db
from financeiro_ml.sku_service import upsert_sku, list_skus, delete_sku, import_excel
from models import Operator
from sqlalchemy.orm import Session as DBSession


def require_master(
    x_operator_id: int | None = Header(default=None, alias="X-Operator-Id"),
    db: DBSession = Depends(get_db),
) -> int:
    """Exige operador Master no backend.

    O frontend envia X-Operator-Id a partir do operador logado no localStorage.
    Não é autenticação forte por token, mas fecha o stub anterior e aplica a mesma
    regra real de operador usada pelo NVS local.
    """
    if not x_operator_id:
        raise HTTPException(status_code=403, detail="Operador Master obrigatório")
    op = db.query(Operator).filter(Operator.id == x_operator_id).first()
    if not op or op.name != "Master":
        raise HTTPException(status_code=403, detail="Operador Master obrigatório")
    return op.id


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
from financeiro_ml.sync import ensure_period_synced
from financeiro_ml.aggregator import aggregate
from financeiro_ml.models import MLOrderCache, MLOrderItemCache, SkuFinanceiro
from sqlalchemy import and_


@router.post("/resumo")
async def get_resumo(params: FilterParams, operator_id: int = Depends(require_master)):
    t0 = time_module.perf_counter()
    trace.info(
        f"START data_inicio={params.data_inicio} data_fim={params.data_fim} "
        f"status={params.status} modalidade={params.modalidade} tipo_frete={params.tipo_frete} "
        f"custo_imposto={params.custo_imposto} sku={params.sku!r} mlb={params.mlb!r} "
        f"frete_comprador={params.considerar_frete_comprador} page={params.page}x{params.page_size}"
    )

    t1 = time_module.perf_counter()
    sync_report = await ensure_period_synced(params.data_inicio, params.data_fim)
    trace.info(
        f"sync.done dias_sincronizados={sync_report['dias_sincronizados']} "
        f"dias_falhos={sync_report['dias_falhos']} novos_orders={sync_report['total_orders']} "
        f"ms={(time_module.perf_counter()-t1)*1000:.0f}"
    )

    from database import SessionLocal
    from sqlalchemy import func
    with SessionLocal() as session:
        date_from = datetime.combine(params.data_inicio, time.min)
        date_to = datetime.combine(params.data_fim, time.max)

        # MT considera a venda como "do dia" quando date_closed (pagamento) cai no dia.
        # Pra status pre-payment (sem date_closed), cai em date_created.
        data_ref = func.coalesce(MLOrderCache.date_closed, MLOrderCache.date_created)
        q = session.query(MLOrderCache).filter(
            and_(data_ref >= date_from, data_ref <= date_to)
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

        tq0 = time_module.perf_counter()
        orders = [_row_to_dict_order(r) for r in q.all()]
        trace.info(f"query.orders count={len(orders)} ms={(time_module.perf_counter()-tq0)*1000:.0f}")
        order_ids = [o["order_id"] for o in orders]

        tq1 = time_module.perf_counter()
        items_q = session.query(MLOrderItemCache).filter(MLOrderItemCache.order_id.in_(order_ids))
        if params.sku:
            items_q = items_q.filter(MLOrderItemCache.seller_sku == params.sku)
        items = [_row_to_dict_item(r) for r in items_q.all()]
        if params.sku:
            eligible_order_ids = {it["order_id"] for it in items}
            orders = [o for o in orders if o["order_id"] in eligible_order_ids]
        trace.info(f"query.items count={len(items)} ms={(time_module.perf_counter()-tq1)*1000:.0f}")

        tq2 = time_module.perf_counter()
        skus_rows = session.query(SkuFinanceiro).all()
        sku_financeiro = {
            r.sku: {"custo_unit": Decimal(str(r.custo_unit)), "imposto_pct": Decimal(str(r.imposto_pct))}
            for r in skus_rows
        }
        trace.info(f"query.skus count={len(sku_financeiro)} ms={(time_module.perf_counter()-tq2)*1000:.0f}")

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

    tagg = time_module.perf_counter()
    result = aggregate(orders, items, sku_financeiro,
                       considerar_frete_comprador=params.considerar_frete_comprador)
    trace.info(
        f"aggregate orders={len(orders)} items={len(items)} "
        f"linhas_tabela={len(result['tabela'])} ms={(time_module.perf_counter()-tagg)*1000:.0f}"
    )

    # Filtro de margem (post-aggregate) — recalcula cards/pizza/tabela baseado na faixa MC%
    if params.margem != "todos":
        result = _apply_margem_filter(result, params.margem)
        trace.info(f"margem.filtrada={params.margem} linhas_pos_filtro={len(result['tabela'])}")

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
    payload = _json_safe(result)
    trace.info(
        f"END vendas_aprovadas={result['cards']['vendas_aprovadas']} "
        f"mc={result['cards']['mc_total']} ({result['cards']['mc_pct_global']}%) "
        f"total_ms={(time_module.perf_counter()-t0)*1000:.0f}"
    )
    return payload


def _apply_margem_filter(result: dict, faixa: str) -> dict:
    """Filtra tabela por faixa de MC% e recalcula cards/pizza baseado nas linhas restantes.

    Faixas:
      bom     → mc_pct >= 13
      atencao → 10 <= mc_pct < 13
      critico → mc_pct < 10
    """
    bands = {
        "bom":     lambda v: v >= 13,
        "atencao": lambda v: 10 <= v < 13,
        "critico": lambda v: v < 10,
    }
    fn = bands.get(faixa)
    if not fn:
        return result

    tabela_f = [r for r in result["tabela"] if fn(float(r["mc_pct"]))]

    def _s(field: str) -> Decimal:
        total = Decimal("0")
        for r in tabela_f:
            total += Decimal(str(r[field]))
        return total

    sum_fatur = _s("faturamento_ml")
    sum_custo = _s("custo")
    sum_imp = _s("imposto")
    sum_tarifa = _s("tarifa")
    sum_fc = _s("frete_comprador")
    sum_fv = _s("frete_vendedor")
    sum_mc = _s("mc")
    qtd_ord = len({r["order_id"] for r in tabela_f})
    qtd_unid = sum(int(r["qty"]) for r in tabela_f)
    sum_produto = sum_fatur - sum_fc  # produto puro = faturamento - frete_comprador

    mc_pct_global = (sum_mc / sum_produto * Decimal("100")) if sum_produto > 0 else Decimal("0")
    ticket_medio = (sum_produto / qtd_ord) if qtd_ord else Decimal("0")
    ticket_mc = (sum_mc / qtd_ord) if qtd_ord else Decimal("0")

    def _q(v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))

    cards_f = {
        **result["cards"],
        "vendas_aprovadas": _q(sum_produto),
        "vendas_canceladas": Decimal("0"),  # filtro só vale pra aprovadas
        "faturamento_ml": _q(sum_fatur),
        "custo_total": _q(sum_custo),
        "imposto_total": _q(sum_imp),
        "custo_imposto_total": _q(sum_custo + sum_imp),
        "tarifa_venda": _q(sum_tarifa),
        "frete_comprador_total": _q(sum_fc),
        "frete_vendedor_total": _q(sum_fv),
        "frete_total": _q(sum_fc + sum_fv),
        "mc_total": _q(sum_mc),
        "mc_pct_global": _q(mc_pct_global),
        "ticket_medio": _q(ticket_medio),
        "ticket_mc": _q(ticket_mc),
        "qtd_vendas_aprovadas": qtd_ord,
        "qtd_vendas_canceladas": 0,
        "qtd_total_vendas": qtd_ord,
        "unidades_aprovadas": qtd_unid,
    }

    pizza_f = []
    if sum_produto > 0:
        pizza_f = [
            {"label": "Custo",   "valor": _q(sum_custo),  "pct": _q(sum_custo / sum_produto * Decimal("100"))},
            {"label": "Imposto", "valor": _q(sum_imp),    "pct": _q(sum_imp / sum_produto * Decimal("100"))},
            {"label": "Tarifa",  "valor": _q(sum_tarifa), "pct": _q(sum_tarifa / sum_produto * Decimal("100"))},
            {"label": "Frete",   "valor": _q(sum_fv),     "pct": _q(sum_fv / sum_produto * Decimal("100"))},
            {"label": "MC",      "valor": _q(sum_mc),     "pct": _q(mc_pct_global)},
        ]

    return {**result, "tabela": tabela_f, "cards": cards_f, "pizza": pizza_f}


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
        "cupom_seller": Decimal(str(r.cupom_seller)) if r.cupom_seller is not None else Decimal("0"),
        "logistic_type": r.logistic_type,
        "shipping_mode": r.shipping_mode,
        "shipment_id": r.shipment_id,
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
    rows = []
    page = 1
    while True:
        full = await get_resumo(params.model_copy(update={"page": page, "page_size": 200}),
                                operator_id=operator_id)
        rows.extend(full["tabela"])
        pagination = full.get("pagination") or {}
        if page >= int(pagination.get("total_pages") or 1):
            break
        page += 1

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
    from financeiro_ml.models import MLTokens
    with SessionLocal() as session:
        token = session.query(MLTokens).first()
        return {
            "ok": True,
            "ml_configured": token is not None,
            "user_id": token.user_id if token else None,
        }


@router.get("/_debug/sync-status")
async def debug_sync_status():
    """Retorna últimos 30 dias de status de sync (incluindo erros). Debug only."""
    from database import SessionLocal
    from financeiro_ml.models import MLDaySyncStatus
    with SessionLocal() as session:
        rows = (
            session.query(MLDaySyncStatus)
            .order_by(MLDaySyncStatus.day.desc())
            .limit(30)
            .all()
        )
        return [
            {
                "day": str(r.day),
                "status": r.status,
                "orders_count": r.orders_count,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                "error_message": r.error_message,
            }
            for r in rows
        ]

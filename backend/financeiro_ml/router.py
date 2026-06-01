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
    seller_id: int
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
from financeiro_ml.aggregator import aggregate
from financeiro_ml.models_v2 import MLOrderCache, MLOrderItemCache, SkuFinanceiro
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

    from financeiro_ml.db import FinSessionLocal as SessionLocal
    from sqlalchemy import func
    with SessionLocal() as session:
        date_from = datetime.combine(params.data_inicio, time.min)
        date_to = datetime.combine(params.data_fim, time.max)

        # MT considera a venda como "do dia" quando date_closed (pagamento) cai no dia.
        # Pra status pre-payment (sem date_closed), cai em date_created.
        data_ref = func.coalesce(MLOrderCache.date_closed, MLOrderCache.date_created)
        q = session.query(MLOrderCache).filter(
            MLOrderCache.seller_id == params.seller_id,
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
        items_q = session.query(MLOrderItemCache).filter(
            MLOrderItemCache.seller_id == params.seller_id,
            MLOrderItemCache.order_id.in_(order_ids),
        )
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


@router.post("/_debug/reset-tokens")
async def debug_reset_tokens():
    """Força reset da row ml_tokens lendo do env (ML_ACCESS_TOKEN/REFRESH_TOKEN/USER_ID).
    Use após atualizar vars no Railway pra propagar pro DB."""
    import os
    from database import SessionLocal
    from financeiro_ml.models import MLTokens
    from datetime import datetime, timedelta
    access = os.getenv("ML_ACCESS_TOKEN")
    refresh = os.getenv("ML_REFRESH_TOKEN")
    user_id = os.getenv("ML_USER_ID")
    if not (access and refresh and user_id):
        return {"ok": False, "error": "env vars ML_ACCESS_TOKEN/REFRESH_TOKEN/USER_ID missing"}
    with SessionLocal() as session:
        row = session.query(MLTokens).first()
        if row is None:
            row = MLTokens(id=1)
            session.add(row)
        row.access_token = access
        row.refresh_token = refresh
        row.user_id = int(user_id)
        row.expires_at = datetime.utcnow() + timedelta(hours=5)
        row.updated_at = datetime.utcnow()
        session.commit()
    return {"ok": True, "user_id": int(user_id), "access_first10": access[:10] + "..."}


@router.get("/_debug/test-token")
async def debug_test_token():
    """Faz UMA chamada ao ML pra validar token. Retorna detalhe do erro se falhar."""
    import httpx
    from financeiro_ml.client import build_default_client
    try:
        client = build_default_client()
        token = await client._ensure_fresh_token()
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                "https://api.mercadolibre.com/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            return {
                "token_first10": token[:10] + "...",
                "token_last5": "..." + token[-5:],
                "users_me_status": resp.status_code,
                "users_me_body": resp.json() if resp.status_code < 500 else resp.text[:500],
            }
    except Exception as e:
        import traceback
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[:2000]}


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


def _coerce_row(model, d: dict) -> dict:
    """Converte um dict (vindo de JSON) nos tipos das colunas do model.
    DateTime/Date viram objetos; Numeric vira Decimal. Ignora colunas ausentes."""
    from sqlalchemy import DateTime, Date, Numeric
    from datetime import datetime as _dt, date as _date
    out = {}
    for col in model.__table__.columns:
        if col.name not in d:
            continue
        v = d[col.name]
        if v is not None:
            if isinstance(col.type, DateTime):
                v = _dt.fromisoformat(v)
            elif isinstance(col.type, Date):
                v = _date.fromisoformat(v)
            elif isinstance(col.type, Numeric):
                v = Decimal(str(v))
        out[col.name] = v
    return out


@router.post("/_debug/import-cache")
async def debug_import_cache(
    payload: dict,
    x_import_secret: str | None = Header(default=None, alias="X-Import-Secret"),
):
    """Importa cache ML de outro ambiente (transferência local→prod). Escopado às 3 tabelas
    ML; UPSERT idempotente. Guard: header X-Import-Secret == ML_CLIENT_SECRET.

    payload = {"orders": [...], "items": [...], "days": [...]}
    - orders: dicts com colunas de ml_orders_cache (raw_json opcional → default '{}').
    - items: dicts de ml_order_items_cache (sem 'id'); regravados por order_id (delete+insert).
    - days: dicts de ml_day_sync_status (chave: day).
    """
    import os
    from database import SessionLocal
    from financeiro_ml.models import MLOrderCache, MLOrderItemCache, MLDaySyncStatus

    secret = os.getenv("ML_CLIENT_SECRET")
    if not secret or x_import_secret != secret:
        raise HTTPException(status_code=403, detail="forbidden")

    orders = payload.get("orders", [])
    items = payload.get("items", [])
    days = payload.get("days", [])

    n_orders = n_items = n_days = 0
    with SessionLocal() as session:
        # ORDERS (upsert por order_id)
        for o in orders:
            row_data = _coerce_row(MLOrderCache, o)
            row_data.setdefault("raw_json", "{}")
            oid = row_data["order_id"]
            existing = session.query(MLOrderCache).filter_by(order_id=oid).first()
            if existing is None:
                session.add(MLOrderCache(**row_data))
            else:
                for k, v in row_data.items():
                    setattr(existing, k, v)
            n_orders += 1

        # ITEMS (regrava por order_id: delete + insert; ignora 'id' de origem)
        order_ids_with_items = {it.get("order_id") for it in items if it.get("order_id") is not None}
        if order_ids_with_items:
            session.query(MLOrderItemCache).filter(
                MLOrderItemCache.order_id.in_(order_ids_with_items)
            ).delete(synchronize_session=False)
        for it in items:
            row_data = _coerce_row(MLOrderItemCache, it)
            row_data.pop("id", None)
            session.add(MLOrderItemCache(**row_data))
            n_items += 1

        # DAYS (upsert por day)
        for drow in days:
            row_data = _coerce_row(MLDaySyncStatus, drow)
            row_data.pop("id", None)
            day_val = row_data["day"]
            existing = session.query(MLDaySyncStatus).filter_by(day=day_val).first()
            if existing is None:
                session.add(MLDaySyncStatus(**row_data))
            else:
                for k, v in row_data.items():
                    setattr(existing, k, v)
            n_days += 1

        session.commit()

    return {"ok": True, "orders": n_orders, "items": n_items, "days": n_days}


# ============ Backfill ============

class BackfillParams(BaseModel):
    seller_id: int
    day_from: date
    day_to: date


@router.post("/backfill")
async def create_backfill(params: BackfillParams, operator_id: int = Depends(require_master)):
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.backfill import create_job
    from financeiro_ml.worker import BackfillTask, get_write_queue
    from datetime import timedelta
    job_id = create_job(FinSessionLocal, seller_id=params.seller_id,
                        day_from=params.day_from, day_to=params.day_to)
    days = [params.day_from + timedelta(days=i)
            for i in range((params.day_to - params.day_from).days + 1)]
    queue = get_write_queue()
    if queue is not None:
        await queue.put(BackfillTask(seller_id=params.seller_id, days=days, job_id=job_id))
    return {"job_id": job_id}


@router.get("/backfill/{job_id}")
async def get_backfill_status(job_id: int, operator_id: int = Depends(require_master)):
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.backfill import get_job
    prog = get_job(FinSessionLocal, job_id)
    if prog is None:
        raise HTTPException(status_code=404, detail="job não encontrado")
    return prog


class OAuthExchangeParams(BaseModel):
    code: str


@router.post("/_debug/ml-oauth-exchange")
async def ml_oauth_exchange(params: OAuthExchangeParams, operator_id: int = Depends(require_master)):
    """Troca um authorization code do ML por tokens novos e grava no banco ISOLADO.
    Usa ML_CLIENT_ID/SECRET/REDIRECT_URI/USER_ID do ambiente. Nunca ecoa os tokens."""
    import os
    import httpx
    from datetime import datetime, timedelta
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.models_v2 import MLTokens

    client_id = os.getenv("ML_CLIENT_ID")
    client_secret = os.getenv("ML_CLIENT_SECRET")
    redirect_uri = os.getenv("ML_REDIRECT_URI")
    user_id = os.getenv("ML_USER_ID")
    if not (client_id and client_secret and redirect_uri and user_id):
        raise HTTPException(status_code=400,
                            detail="env ML_CLIENT_ID/SECRET/REDIRECT_URI/USER_ID ausente")

    async with httpx.AsyncClient(timeout=20) as http:
        resp = await http.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": params.code,
                "redirect_uri": redirect_uri,
            },
        )
    if resp.status_code != 200:
        ct = resp.headers.get("content-type", "")
        return {"ok": False, "ml_status": resp.status_code,
                "ml_error": resp.json() if ct.startswith("application/json") else resp.text[:300]}

    data = resp.json()
    seller_id = int(user_id)
    s = FinSessionLocal()
    try:
        row = s.query(MLTokens).filter_by(seller_id=seller_id).first()
        if row is None:
            row = MLTokens(seller_id=seller_id)
            s.add(row)
        row.access_token = data["access_token"]
        row.refresh_token = data["refresh_token"]
        row.expires_at = datetime.utcnow() + timedelta(seconds=int(data.get("expires_in", 21600)))
        row.client_id = client_id
        row.updated_at = datetime.utcnow()
        s.commit()
    finally:
        s.close()
    return {"ok": True, "seller_id": seller_id, "expires_in": data.get("expires_in")}


class ProbeSearchParams(BaseModel):
    data: str  # YYYY-MM-DD


class CanaryOrdersSearchParams(BaseModel):
    seller_id: int
    data: date
    max_pages: int = Field(default=20, ge=1, le=40)


class CanaryProcessPendingParams(BaseModel):
    seller_id: int
    max_tasks: int = Field(default=5, ge=1, le=10)
    sleep_sec: float = Field(default=0, ge=0, le=30)


class CanaryBillingOrderDetailsParams(BaseModel):
    seller_id: int
    max_orders: int = Field(default=5, ge=1, le=20)


class CanaryBillingOrderIdsParams(BaseModel):
    seller_id: int
    order_ids: list[int] = Field(min_length=1, max_length=20)


@router.post("/_debug/canary/orders-search")
async def canary_orders_search(params: CanaryOrdersSearchParams,
                               operator_id: int = Depends(require_master)):
    """Canario V2 Light: chama apenas /orders/search por data.

    Nao chama shipments/costs e nao alimenta o cache do painel. Grava snapshots
    isolados + pendencias para medir o fluxo sem contaminar margem financeira.
    """
    from financeiro_ml.db import FinSessionLocal, init_fin_db
    from financeiro_ml.client import build_default_client
    from financeiro_ml.canary import run_orders_search_canary

    init_fin_db()
    client = build_default_client(seller_id=params.seller_id)
    result = await run_orders_search_canary(
        session_factory=FinSessionLocal,
        client=client,
        seller_id=params.seller_id,
        day=params.data,
        max_pages=params.max_pages,
    )
    return result.as_dict()


@router.post("/_debug/canary/{run_id}/billing-order-details")
async def canary_billing_order_details(run_id: int, params: CanaryBillingOrderDetailsParams,
                                       operator_id: int = Depends(require_master)):
    """Canario billing: valida vinculo order_id/shipping_id sem chamar shipments."""
    from financeiro_ml.db import FinSessionLocal, init_fin_db
    from financeiro_ml.client import build_default_client
    from financeiro_ml.canary import run_billing_order_details_canary

    init_fin_db()
    client = build_default_client(seller_id=params.seller_id)
    result = await run_billing_order_details_canary(
        session_factory=FinSessionLocal,
        client=client,
        run_id=run_id,
        seller_id=params.seller_id,
        max_orders=params.max_orders,
    )
    return result.as_dict()


@router.post("/_debug/canary/billing-order-ids")
async def canary_billing_order_ids(params: CanaryBillingOrderIdsParams,
                                   operator_id: int = Depends(require_master)):
    """Canario billing para order_ids explicitos. Nao chama shipments."""
    from financeiro_ml.db import init_fin_db
    from financeiro_ml.client import build_default_client
    from financeiro_ml.canary import run_billing_order_ids_canary

    init_fin_db()
    client = build_default_client(seller_id=params.seller_id)
    result = await run_billing_order_ids_canary(
        client=client,
        seller_id=params.seller_id,
        order_ids=params.order_ids,
    )
    return result.as_dict()


@router.post("/_debug/canary/{run_id}/process-pending")
async def canary_process_pending(run_id: int, params: CanaryProcessPendingParams,
                                 operator_id: int = Depends(require_master)):
    """Canario V2 Light: processa poucas pendencias, uma por vez.

    Para no primeiro 429. Nao roda automaticamente.
    """
    from financeiro_ml.db import FinSessionLocal, init_fin_db
    from financeiro_ml.client import build_default_client
    from financeiro_ml.canary import process_canary_pending

    init_fin_db()
    client = build_default_client(seller_id=params.seller_id)
    result = await process_canary_pending(
        session_factory=FinSessionLocal,
        client=client,
        run_id=run_id,
        max_tasks=params.max_tasks,
        sleep_sec=params.sleep_sec,
    )
    return result.as_dict()


@router.get("/_debug/canary/{run_id}")
async def get_canary(run_id: int, operator_id: int = Depends(require_master)):
    from financeiro_ml.db import FinSessionLocal, init_fin_db
    from financeiro_ml.canary import get_canary_run

    init_fin_db()
    result = get_canary_run(FinSessionLocal, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="canario nao encontrado")
    return result


@router.post("/_debug/probe-search")
async def probe_search(params: ProbeSearchParams, operator_id: int = Depends(require_master)):
    """Fase 0b da investigação 429: 1 chamada CRUA a /orders/search (limit=1, SEM
    retry/backoff/enriquecimento), devolvendo status + headers diagnósticos + corpo +
    http_version + IP de egress + o client_id dono do token. NÃO grava nada.
    Revela se o 429 é cota da API (corpo local_rate_limited) ou bloqueio de borda (cf-ray)."""
    import os
    import httpx
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.models_v2 import MLTokens

    seller_id = int(os.getenv("ML_USER_ID", "0"))
    s = FinSessionLocal()
    try:
        tok = s.query(MLTokens).filter_by(seller_id=seller_id).first()
        token_client_id = tok.client_id if tok else None
        has_token = tok is not None
    finally:
        s.close()
    if not has_token:
        raise HTTPException(status_code=400, detail="sem token no banco isolado")

    # garante token FRESCO (refresca se expirado) — também testa se o refresh_token ainda vive
    from financeiro_ml.client import build_default_client
    try:
        access_token = await build_default_client(seller_id=seller_id)._ensure_fresh_token()
    except Exception as exc:
        return {"step": "refresh_falhou", "token_client_id": token_client_id,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    day = params.data
    q = {
        "seller": seller_id,
        "order.date_created.from": f"{day}T00:00:00.000-03:00",
        "order.date_created.to": f"{day}T23:59:59.000-03:00",
        "offset": 0, "limit": 1,
    }
    egress_ip = "unknown"
    async with httpx.AsyncClient(timeout=20) as http:
        try:
            egress_ip = (await http.get("https://api.ipify.org")).text.strip()
        except Exception:
            pass
        resp = await http.get(
            "https://api.mercadolibre.com/orders/search",
            params=q,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    diag_keys = ("content-type", "retry-after", "cf-ray", "cf-mitigated", "server",
                 "via", "x-cache", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")
    return {
        "step": "search",
        "status": resp.status_code,
        "http_version": resp.http_version,
        "egress_ip": egress_ip,
        "token_client_id": token_client_id,
        "headers": {k: resp.headers.get(k) for k in diag_keys if resp.headers.get(k)},
        "body": resp.text[:800],
    }

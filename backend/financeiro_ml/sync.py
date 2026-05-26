"""Sincronização de cache ML por dia. Política de freshness."""
from datetime import date, datetime, timedelta, timezone

# Timezone fixo da operação Antigra. MT mostra tudo nesse fuso.
# ML retorna `date_created` no offset original do pedido (varia: -04:00, -03:00, etc).
# Armazenamos SEMPRE convertido pra BRT naive — alinha com a UI e com filtros SQL date().
BRT = timezone(timedelta(hours=-3))


def _to_brt_naive(iso_str: str | None) -> datetime | None:
    """Converte ISO datetime (qualquer fuso) → datetime naive em BRT (-03:00).

    Necessário porque ML pode retornar `date_created` em -04:00 (vendas que aparecem
    no dia anterior se armazenadas sem conversão).
    """
    if not iso_str:
        return None
    s = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.astimezone(BRT).replace(tzinfo=None)


def _date_range(start: date, end: date) -> list[date]:
    """Lista inclusiva de datas entre start e end."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _days_needing_sync(days: list[date], statuses: dict[date, object]) -> list[date]:
    """Aplica política de freshness e retorna apenas os dias que precisam re-sync.

    Regras:
    - day == today → re-sync se cache > 5 minutos (não sempre).
    - day in [today-7, today-1] e last_synced_at > 24h → sim.
    - day < today-7 e status == 'ok' → não.
    - day < today-7 e status == 'failed' → sim.
    - day sem status → sim.
    """
    today = date.today()
    threshold_recent = today - timedelta(days=7)
    now = datetime.utcnow()
    needed = []
    for d in days:
        st = statuses.get(d)
        if st is None:
            needed.append(d)
            continue
        if st.status == "failed":
            needed.append(d)
            continue
        if d == today:
            # Hoje: cache de 5 minutos. Re-sync busca apenas pedidos NOVOS.
            if now - st.last_synced_at > timedelta(minutes=5):
                needed.append(d)
            continue
        if d >= threshold_recent:
            if now - st.last_synced_at > timedelta(hours=24):
                needed.append(d)
    return needed


import asyncio
import json
import os
from decimal import Decimal

from database import SessionLocal
from financeiro_ml.models import MLDaySyncStatus, MLOrderCache, MLOrderItemCache
from financeiro_ml.client import build_default_client


async def ensure_period_synced(date_from: date, date_to: date) -> dict:
    """Orquestra sync por dia. Retorna {dias_sincronizados, dias_falhos, total_orders}.

    IMPORTANTE: estende a janela 1 dia pra trás. Justificativa: MT (e nossa query) filtra
    venda por `date_closed`. Pedidos criados ontem mas pagos hoje aparecem no filtro de "hoje",
    mas ML/orders/search filtra por `date_created`. Precisamos puxar o dia anterior também
    pra ter esses pedidos cacheados antes da agregação.
    """
    import logging
    trace = logging.getLogger("financeiro_ml.trace")

    # Estende 1 dia pra trás pra cobrir pedidos created=ontem, closed=hoje
    sync_from = date_from - timedelta(days=1)
    days = _date_range(sync_from, date_to)

    with SessionLocal() as session:
        statuses_rows = session.query(MLDaySyncStatus).filter(
            MLDaySyncStatus.day.in_(days)
        ).all()
        statuses = {s.day: s for s in statuses_rows}

    needed = _days_needing_sync(days, statuses)
    trace.info(
        f"sync.check periodo=[{date_from}..{date_to}] dias_total={len(days)} "
        f"dias_cacheados={len(statuses)} dias_a_sincronizar={len(needed)} "
        f"detalhe_needed={[str(d) for d in needed]}"
    )

    if not needed:
        trace.info("sync.cache_hit (todos os dias estao fresh)")
        return {"dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0}

    max_parallel = int(os.getenv("ML_SYNC_MAX_DAYS_PARALLEL", "5"))
    sem = asyncio.Semaphore(max_parallel)
    client = build_default_client()

    async def sync_one(d: date):
        async with sem:
            return await _sync_single_day(client, d)

    results = await asyncio.gather(*[sync_one(d) for d in needed], return_exceptions=True)
    sucessos = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
    falhas = len(results) - sucessos
    total = sum(r.get("orders_count", 0) for r in results if isinstance(r, dict))
    return {"dias_sincronizados": sucessos, "dias_falhos": falhas, "total_orders": total}


async def _sync_single_day(client, d: date) -> dict:
    """Sincroniza um dia: busca orders, detalha cada um, insere no cache."""
    import logging, time as time_module
    trace = logging.getLogger("financeiro_ml.trace")

    inicio = datetime(d.year, d.month, d.day, 0, 0, 0)
    fim = datetime(d.year, d.month, d.day, 23, 59, 59)
    orders_count = 0
    t_day = time_module.perf_counter()
    try:
        offset = 0
        while True:
            page = await client.search_orders(date_from=inicio, date_to=fim, offset=offset, limit=50)
            results = page.get("results", [])
            if not results:
                break
            # Paralelismo dentro da página com semáforo configurável
            max_parallel_orders = int(os.getenv("ML_SYNC_MAX_ORDERS_PARALLEL", "10"))
            order_sem = asyncio.Semaphore(max_parallel_orders)

            async def _bounded(o):
                async with order_sem:
                    return await _save_order(client, o)

            t_page = time_module.perf_counter()
            await asyncio.gather(*[_bounded(o) for o in results], return_exceptions=True)
            trace.info(
                f"sync.day[{d}] page offset={offset} fetched={len(results)} "
                f"ms_page={(time_module.perf_counter()-t_page)*1000:.0f}"
            )
            orders_count += len(results)
            if len(results) < 50:
                break
            offset += 50

        with SessionLocal() as session:
            st = session.query(MLDaySyncStatus).filter_by(day=d).first()
            if st is None:
                st = MLDaySyncStatus(day=d, last_synced_at=datetime.utcnow(),
                                       orders_count=orders_count, status="ok")
                session.add(st)
            else:
                st.last_synced_at = datetime.utcnow()
                st.orders_count = orders_count
                st.status = "ok"
                st.error_message = None
            session.commit()
        trace.info(
            f"sync.day[{d}] DONE orders_total={orders_count} "
            f"ms_total={(time_module.perf_counter()-t_day)*1000:.0f}"
        )
        return {"status": "ok", "orders_count": orders_count}
    except Exception as e:
        with SessionLocal() as session:
            st = session.query(MLDaySyncStatus).filter_by(day=d).first()
            if st is None:
                st = MLDaySyncStatus(day=d, last_synced_at=datetime.utcnow(),
                                       orders_count=0, status="failed", error_message=str(e))
                session.add(st)
            else:
                st.last_synced_at = datetime.utcnow()
                st.status = "failed"
                st.error_message = str(e)
            session.commit()
        return {"status": "failed", "orders_count": 0, "error": str(e)}


async def _save_order(client, search_result: dict, *, force_refresh: bool = False) -> None:
    """Salva um order do search result no cache. Skip se já existe (ou força refresh).

    Otimização: usa payload do /orders/search direto. Evita call extra a /orders/{id}
    e /items/{id} (campos `status`, `payments`, `order_items[].listing_type_id` já vêm).
    Só faz 1 call extra: /shipments/{id} (cost/list_cost/logistic_type/mode).
    """
    order_id = search_result["id"]

    # Skip se já existe (a menos que force_refresh)
    if not force_refresh:
        with SessionLocal() as session:
            if session.query(MLOrderCache).filter_by(order_id=order_id).first():
                return

    detail = search_result  # usa payload do search direto

    shipment_id = (detail.get("shipping") or {}).get("id")
    shipment = await client.get_shipment(shipment_id) if shipment_id else {}

    # Calcula totais
    produto_total = Decimal("0")
    tarifa_bruta = Decimal("0")
    for it in detail.get("order_items", []):
        produto_total += Decimal(str(it["unit_price"])) * Decimal(it["quantity"])
        tarifa_bruta += Decimal(str(it.get("sale_fee", 0))) * Decimal(it["quantity"])

    # MT calcula frete_vendedor = list_cost − cost (subsídio absorvido pelo seller),
    # não o list_cost cheio. Validado contra 7 ordens aleatórias (universal).
    so = shipment.get("shipping_option") or {}
    frete_comprador = Decimal(str(so.get("cost", 0) or 0))
    list_cost = Decimal(str(so.get("list_cost", 0) or 0))
    frete_vendedor = max(Decimal("0"), list_cost - frete_comprador)

    refund_total = Decimal("0")
    for refund in (detail.get("payments") or []):
        refund_total += Decimal(str(refund.get("transaction_amount_refunded", 0) or 0))

    is_total_cancel = detail.get("status") == "cancelled"
    refund_partial = Decimal("0") if is_total_cancel else refund_total

    # Cupom seller (de campanha ML) — só quando tag `order_has_discount` está presente,
    # pra evitar call desnecessária aos ~70% de orders sem cupom.
    cupom_seller = Decimal("0")
    if "order_has_discount" in (detail.get("tags") or []):
        disc = await client.get_order_discounts(order_id)
        for det in (disc.get("details") or []):
            if det.get("type") == "coupon":
                for it in (det.get("items") or []):
                    cupom_seller += Decimal(str((it.get("amounts") or {}).get("seller") or 0))

    logistic_type = shipment.get("logistic_type")
    shipping_mode = shipment.get("mode")

    # Bucket pra breakdown logístico
    from financeiro_ml.aggregator import _logistic_bucket
    bucket = _logistic_bucket(logistic_type, shipping_mode)

    # Modalidade do anúncio (listing_type_id) — já vem no search response
    first_item = (detail.get("order_items") or [{}])[0]
    modalidade = first_item.get("listing_type_id")

    with SessionLocal() as session:
        existing = session.query(MLOrderCache).filter_by(order_id=order_id).first()
        if existing is None:
            row = MLOrderCache(
                order_id=order_id,
                date_created=_to_brt_naive(detail["date_created"]),
                date_closed=_to_brt_naive(detail.get("date_closed")),
                status=detail["status"],
                status_detail=detail.get("status_detail"),
                produto_total=produto_total,
                frete_comprador=frete_comprador,
                frete_vendedor=frete_vendedor,
                tarifa_bruta=tarifa_bruta,
                tarifa_refund=Decimal("0"),  # TODO refinar quando endpoint billing disponível
                refund_amount_partial=refund_partial,
                cupom_seller=cupom_seller,
                modalidade_anuncio=modalidade,
                logistic_type=logistic_type,
                shipping_mode=shipping_mode,
                breakdown_bucket=bucket,
                raw_json=json.dumps(detail),
                synced_at=datetime.utcnow(),
            )
            session.add(row)
            # Itens
            for it in detail.get("order_items", []):
                session.add(MLOrderItemCache(
                    order_id=order_id,
                    item_id=it["item"]["id"],
                    title=it["item"].get("title", ""),
                    seller_sku=it["item"].get("seller_custom_field") or it["item"].get("seller_sku"),
                    quantity=it["quantity"],
                    unit_price=Decimal(str(it["unit_price"])),
                    category_id=it["item"].get("category_id"),
                ))
        else:
            existing.status = detail["status"]
            existing.refund_amount_partial = refund_partial
            existing.synced_at = datetime.utcnow()
            existing.raw_json = json.dumps(detail)
        session.commit()

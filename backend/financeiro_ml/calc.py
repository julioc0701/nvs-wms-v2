"""Cálculo PURO de uma order ML → dict de campos do cache. Sem I/O, sem commit.

Migra a inteligência validada de sync.py:_save_order. Recebe os payloads já
buscados (order do search + shipment + shipment_costs + discounts) e devolve
um dict pronto pra upsert. Testável sem rede.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

BRT = timezone(timedelta(hours=-3))


def _to_brt_naive(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    s = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.astimezone(BRT).replace(tzinfo=None)


def _looks_human_sku(s: str | None) -> bool:
    if not s:
        return False
    return not (s.startswith("MLB") and "_" in s)


def _seller_sku_from_item(order_item: dict) -> str | None:
    item = order_item.get("item") or {}
    sku_cf = item.get("seller_custom_field")
    sku_sku = item.get("seller_sku")
    if _looks_human_sku(sku_sku):
        return sku_sku
    if _looks_human_sku(sku_cf):
        return sku_cf
    return sku_cf or sku_sku


def build_order_row(*, seller_id: int, order: dict, shipment: dict,
                    shipment_costs: dict, discounts: dict) -> dict:
    from financeiro_ml.aggregator import _logistic_bucket

    order_id = order["id"]
    produto_total = Decimal("0")
    tarifa_bruta = Decimal("0")
    for it in order.get("order_items", []):
        produto_total += Decimal(str(it["unit_price"])) * Decimal(it["quantity"])
        tarifa_bruta += Decimal(str(it.get("sale_fee", 0))) * Decimal(it["quantity"])

    so = shipment.get("shipping_option") or {}
    frete_comprador = Decimal(str(so.get("cost", 0) or 0))
    list_cost = Decimal(str(so.get("list_cost", 0) or 0))
    frete_vendedor = max(Decimal("0"), list_cost - frete_comprador)
    logistic_type = shipment.get("logistic_type")
    shipping_mode = shipment.get("mode")
    shipment_id = (order.get("shipping") or {}).get("id")
    frete_incerto = False

    if frete_comprador == 0 and shipment_id:
        if shipment_costs:
            receiver = shipment_costs.get("receiver") or {}
            sender = (shipment_costs.get("senders") or [{}])[0]
            sender_cost = Decimal(str(sender.get("cost") or 0))
            sender_save = Decimal(str(sender.get("save") or 0))
            disc_types = {d.get("type") for d in (receiver.get("discounts") or [])}
            if "loyal" in disc_types and sender_cost == 0:
                frete_comprador = Decimal(str(receiver.get("save") or 0))
            elif ("ratio" in disc_types and sender_cost > 0 and sender_save > 0
                  and logistic_type == "self_service"):
                frete_comprador = sender_save
        else:
            # bug 4: costs indisponível → não assume 0 cego, marca incerteza
            frete_incerto = True

    refund_total = Decimal("0")
    for pay in (order.get("payments") or []):
        refund_total += Decimal(str(pay.get("transaction_amount_refunded", 0) or 0))
    is_total_cancel = order.get("status") == "cancelled"
    refund_partial = Decimal("0") if is_total_cancel else refund_total

    cupom_seller = Decimal("0")
    for det in (discounts.get("details") or []):
        if det.get("type") == "coupon":
            for it in (det.get("items") or []):
                cupom_seller += Decimal(str((it.get("amounts") or {}).get("seller") or 0))

    bucket = _logistic_bucket(logistic_type, shipping_mode)
    first_item = (order.get("order_items") or [{}])[0]
    modalidade = first_item.get("listing_type_id")

    items = []
    for it in order.get("order_items", []):
        item = it["item"]
        items.append({
            "seller_id": seller_id, "order_id": order_id, "item_id": item["id"],
            "title": item.get("title", ""), "seller_sku": _seller_sku_from_item(it),
            "quantity": it["quantity"], "unit_price": Decimal(str(it["unit_price"])),
            "category_id": item.get("category_id"),
        })

    return {
        "seller_id": seller_id, "order_id": order_id,
        "date_created": _to_brt_naive(order["date_created"]),
        "date_closed": _to_brt_naive(order.get("date_closed")),
        "date_last_updated": _to_brt_naive(
            order.get("date_last_updated") or order.get("last_updated")),
        "status": order["status"], "status_detail": order.get("status_detail"),
        "produto_total": produto_total, "frete_comprador": frete_comprador,
        "frete_vendedor": frete_vendedor, "tarifa_bruta": tarifa_bruta,
        "tarifa_refund": Decimal("0"), "refund_amount_partial": refund_partial,
        "cupom_seller": cupom_seller, "modalidade_anuncio": modalidade,
        "logistic_type": logistic_type, "shipping_mode": shipping_mode,
        "shipment_id": shipment_id, "breakdown_bucket": bucket,
        "frete_incerto": frete_incerto, "items": items,
    }

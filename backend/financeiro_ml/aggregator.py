"""Agregador puro. Sem I/O. Recebe dados, devolve KPIs e tabela.

Implementa as fórmulas validadas em Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md §3.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

ME1_OR_OUTROS_BUCKETS = {"me1", "outros"}


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_line_mc(*, produto_total: Decimal, frete_comprador: Decimal,
                     frete_vendedor: Decimal, custo: Decimal, imposto: Decimal,
                     tarifa_liquida: Decimal, refund_parcial: Decimal,
                     logistic_type: str | None, shipping_mode: str | None,
                     considerar_frete_comprador: bool = False,
                     cupom_seller: Decimal = Decimal("0")) -> dict:
    """Calcula MC e MC% pra uma linha de venda.

    Regra: frete_comprador é subtraído da base salvo quando modalidade é ME1
    ou "Outro (a combinar)" — nestes casos o vendedor absorve o frete.
    Se considerar_frete_comprador=True, sempre usa vendas_aprovadas_linha como base.
    `cupom_seller` reduz tanto o faturamento quanto a base de MC (campanhas ML
    onde o seller paga o desconto).
    """
    bucket = _logistic_bucket(logistic_type, shipping_mode)
    keeps_buyer_freight = considerar_frete_comprador or bucket in ME1_OR_OUTROS_BUCKETS

    # Faturamento líquido — subtrai cupom seller (desconto que o seller banca)
    vendas_aprovadas_linha = produto_total + frete_comprador - cupom_seller

    if keeps_buyer_freight:
        base = vendas_aprovadas_linha
    else:
        base = produto_total - cupom_seller

    mc = base - custo - imposto - tarifa_liquida - frete_vendedor - refund_parcial
    mc_pct = (mc / produto_total * Decimal("100")) if produto_total > 0 else Decimal("0")

    return {
        "mc": _q(mc),
        "mc_pct": _q(mc_pct),
        "vendas_aprovadas_linha": _q(vendas_aprovadas_linha),
    }


from collections import defaultdict


def aggregate(orders: list[dict], items: list[dict], sku_financeiro: dict[str, dict], *,
              considerar_frete_comprador: bool = False) -> dict:
    """Agrega lista de orders + itens + cadastro SKU em KPIs prontos.

    Retorna: {cards, pizza, tabela}.
    """
    items_by_order: dict[int, list[dict]] = defaultdict(list)
    for it in items:
        items_by_order[it["order_id"]].append(it)

    tabela_linhas = []
    sum_aprovadas = Decimal("0")
    sum_canceladas = Decimal("0")
    sum_custo = Decimal("0")
    sum_imposto = Decimal("0")
    sum_tarifa = Decimal("0")
    sum_frete_comprador = Decimal("0")
    sum_frete_vendedor = Decimal("0")
    sum_refund_partial = Decimal("0")
    sum_mc = Decimal("0")
    qtd_aprovadas = 0
    qtd_canceladas = 0
    units_aprovadas = 0
    units_canceladas = 0
    buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for order in orders:
        order_items = items_by_order.get(order["order_id"], [])
        is_aprovada = order["status"] == "paid"
        is_cancelada = order["status"] == "cancelled"

        # Custo e imposto agregados de todos os itens do pedido
        custo_order = Decimal("0")
        imposto_order = Decimal("0")
        unidades = 0
        for it in order_items:
            sku = (it.get("seller_sku") or "").strip()
            fin = sku_financeiro.get(sku, {"custo_unit": Decimal("0"), "imposto_pct": Decimal("0")})
            custo_order += fin["custo_unit"] * Decimal(it["quantity"])
            unidades += it["quantity"]
        # Imposto incide sobre o produto puro do pedido
        # Se vários itens com aliquota diferente, simplifica: aliquota = média ponderada pelo valor
        if order["produto_total"] > 0:
            imposto_sum_weighted = Decimal("0")
            for it in order_items:
                sku = (it.get("seller_sku") or "").strip()
                fin = sku_financeiro.get(sku, {"imposto_pct": Decimal("0")})
                linha_valor = it["unit_price"] * Decimal(it["quantity"])
                imposto_sum_weighted += linha_valor * fin["imposto_pct"] / Decimal("100")
            imposto_order = imposto_sum_weighted

        tarifa_liquida = order["tarifa_bruta"] - order["tarifa_refund"]

        line_mc = compute_line_mc(
            produto_total=order["produto_total"],
            frete_comprador=order["frete_comprador"],
            frete_vendedor=order["frete_vendedor"],
            custo=custo_order,
            imposto=imposto_order,
            tarifa_liquida=tarifa_liquida,
            refund_parcial=order["refund_amount_partial"],
            logistic_type=order.get("logistic_type"),
            shipping_mode=order.get("shipping_mode"),
            considerar_frete_comprador=considerar_frete_comprador,
            cupom_seller=order.get("cupom_seller", Decimal("0")) or Decimal("0"),
        )

        # Para tabela: 1 linha por item (igual MT)
        for it in order_items:
            tabela_linhas.append({
                "order_id": order["order_id"],
                "anuncio": it["title"],
                "sku": it.get("seller_sku") or "",
                "data": order["date_created"].isoformat(),
                "frete_label": order.get("breakdown_bucket", "outros"),
                "valor_unit": _q(it["unit_price"]),
                "qty": it["quantity"],
                "faturamento_ml": line_mc["vendas_aprovadas_linha"],
                "custo": _q(custo_order * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "imposto": _q(imposto_order * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "tarifa": _q(tarifa_liquida * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "frete_comprador": _q(order["frete_comprador"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "frete_vendedor": _q(order["frete_vendedor"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "mc": _q(line_mc["mc"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "mc_pct": line_mc["mc_pct"],
            })

        if is_aprovada:
            sum_aprovadas += line_mc["vendas_aprovadas_linha"]
            sum_custo += custo_order
            sum_imposto += imposto_order
            sum_tarifa += tarifa_liquida
            sum_frete_comprador += order["frete_comprador"]
            sum_frete_vendedor += order["frete_vendedor"]
            sum_refund_partial += order["refund_amount_partial"]
            sum_mc += line_mc["mc"]
            qtd_aprovadas += 1
            units_aprovadas += unidades
            buckets[order.get("breakdown_bucket", "outros")] += line_mc["vendas_aprovadas_linha"]
        elif is_cancelada:
            sum_canceladas += line_mc["vendas_aprovadas_linha"]
            qtd_canceladas += 1
            units_canceladas += unidades

    faturamento_ml = sum_aprovadas + sum_canceladas
    ticket_medio = (sum_aprovadas / qtd_aprovadas) if qtd_aprovadas else Decimal("0")
    ticket_mc = (sum_mc / qtd_aprovadas) if qtd_aprovadas else Decimal("0")
    mc_pct_global = (sum_mc / sum_aprovadas * Decimal("100")) if sum_aprovadas else Decimal("0")

    cards = {
        "vendas_aprovadas": _q(sum_aprovadas),
        "vendas_canceladas": _q(sum_canceladas),
        "faturamento_ml": _q(faturamento_ml),
        "custo_total": _q(sum_custo),
        "imposto_total": _q(sum_imposto),
        "custo_imposto_total": _q(sum_custo + sum_imposto),
        "tarifa_venda": _q(sum_tarifa),
        "frete_comprador_total": _q(sum_frete_comprador),
        "frete_vendedor_total": _q(sum_frete_vendedor),
        "frete_total": _q(sum_frete_comprador + sum_frete_vendedor),
        "mc_total": _q(sum_mc),
        "mc_pct_global": _q(mc_pct_global),
        "ticket_medio": _q(ticket_medio),
        "ticket_mc": _q(ticket_mc),
        "qtd_vendas_aprovadas": qtd_aprovadas,
        "qtd_vendas_canceladas": qtd_canceladas,
        "qtd_total_vendas": qtd_aprovadas + qtd_canceladas,
        "unidades_aprovadas": units_aprovadas,
        "unidades_canceladas": units_canceladas,
        "devolucoes_parciais_valor": _q(sum_refund_partial),
        "breakdown_logistico": {k: _q(v) for k, v in buckets.items()},
    }

    base_pizza = sum_aprovadas
    pizza = []
    if base_pizza > 0:
        pizza = [
            {"label": "Custo", "valor": _q(sum_custo), "pct": _q(sum_custo / base_pizza * Decimal("100"))},
            {"label": "Imposto", "valor": _q(sum_imposto), "pct": _q(sum_imposto / base_pizza * Decimal("100"))},
            {"label": "Tarifa", "valor": _q(sum_tarifa), "pct": _q(sum_tarifa / base_pizza * Decimal("100"))},
            {"label": "Frete", "valor": _q(sum_frete_vendedor), "pct": _q(sum_frete_vendedor / base_pizza * Decimal("100"))},
            {"label": "MC", "valor": _q(sum_mc), "pct": _q(mc_pct_global)},
        ]

    return {
        "cards": cards,
        "pizza": pizza,
        "tabela": tabela_linhas,
    }


def _logistic_bucket(logistic_type: str | None, shipping_mode: str | None) -> str:
    """Mapeia campos ML pra bucket do breakdown logístico.

    Mapping inicial — refinar quando testes ML revelarem combinações reais.
    """
    if shipping_mode == "me1":
        return "me1"
    if logistic_type == "fulfillment":
        return "full"
    if logistic_type == "self_service":
        return "flex"
    if logistic_type in ("drop_off", "cross_docking"):
        return "places_coleta"
    return "outros"

from decimal import Decimal
from datetime import datetime
from financeiro_ml.aggregator import compute_line_mc, aggregate


def test_mc_line_full_modality_subtracts_buyer_freight():
    """Validação contra linha SKU 577 do print do MT.
    Valor unit 26,99 × 1, Frete Full (não ME1).
    Vendas Aprovadas (faturamento ML) = 45,98 (produto+frete_comprador).
    Custo 8,46; Imposto 2,43; Tarifa 3,24; Frete Comprador 18,99; Frete Vendedor 6,55.
    Resultado esperado: MC = 6,31; MC% = 23,38%.
    """
    result = compute_line_mc(
        produto_total=Decimal("26.99"),
        frete_comprador=Decimal("18.99"),
        frete_vendedor=Decimal("6.55"),
        custo=Decimal("8.46"),
        imposto=Decimal("2.43"),
        tarifa_liquida=Decimal("3.24"),
        refund_parcial=Decimal("0"),
        logistic_type="fulfillment",   # → bucket Full → não-ME1
        shipping_mode="me2",
    )
    assert result["mc"] == Decimal("6.31")
    assert result["mc_pct"] == Decimal("23.38")


def test_mc_line_me1_keeps_buyer_freight():
    """Em ME1 o frete comprador NÃO é subtraído."""
    result = compute_line_mc(
        produto_total=Decimal("26.99"),
        frete_comprador=Decimal("18.99"),
        frete_vendedor=Decimal("6.55"),
        custo=Decimal("8.46"),
        imposto=Decimal("2.43"),
        tarifa_liquida=Decimal("3.24"),
        refund_parcial=Decimal("0"),
        logistic_type=None,
        shipping_mode="me1",
    )
    # MC = (26.99+18.99) - 8.46 - 2.43 - 3.24 - 6.55 = 25.30
    assert result["mc"] == Decimal("25.30")


def test_aggregate_two_orders_one_approved_one_cancelled():
    orders = [
        {
            "order_id": 1, "status": "paid", "date_created": datetime(2026, 5, 26),
            "produto_total": Decimal("26.99"), "frete_comprador": Decimal("18.99"),
            "frete_vendedor": Decimal("6.55"), "tarifa_bruta": Decimal("3.24"),
            "tarifa_refund": Decimal("0"), "refund_amount_partial": Decimal("0"),
            "logistic_type": "fulfillment", "shipping_mode": "me2",
            "modalidade_anuncio": "gold_pro", "breakdown_bucket": "full",
        },
        {
            "order_id": 2, "status": "cancelled", "date_created": datetime(2026, 5, 26),
            "produto_total": Decimal("100.00"), "frete_comprador": Decimal("0"),
            "frete_vendedor": Decimal("0"), "tarifa_bruta": Decimal("0"),
            "tarifa_refund": Decimal("0"), "refund_amount_partial": Decimal("0"),
            "logistic_type": "fulfillment", "shipping_mode": "me2",
            "modalidade_anuncio": "gold_pro", "breakdown_bucket": "full",
        },
    ]
    items = [
        {"order_id": 1, "seller_sku": "577", "quantity": 1, "unit_price": Decimal("26.99"),
         "item_id": "MLB1", "title": "Retrovisor 577"},
        {"order_id": 2, "seller_sku": "999", "quantity": 1, "unit_price": Decimal("100.00"),
         "item_id": "MLB2", "title": "Outro"},
    ]
    sku_financeiro = {
        "577": {"custo_unit": Decimal("8.46"), "imposto_pct": Decimal("9.00")},
        "999": {"custo_unit": Decimal("50.00"), "imposto_pct": Decimal("9.00")},
    }
    result = aggregate(orders, items, sku_financeiro)
    cards = result["cards"]
    # Cards globais MT NÃO incluem frete_comprador. Order 1 só conta valor produto.
    assert cards["vendas_aprovadas"] == Decimal("26.99")     # só order 1, sem frete_comp
    assert cards["vendas_canceladas"] == Decimal("100.00")   # order 2, sem frete
    assert cards["faturamento_ml"] == Decimal("126.99")      # 26.99 + 100.00
    assert cards["qtd_vendas_aprovadas"] == 1
    assert cards["qtd_vendas_canceladas"] == 1


def test_aggregate_with_considerar_frete_comprador():
    """Quando considerar_frete_comprador=True, MC global usa vendas_aprovadas como base sempre.

    Order 1 usa logistic_type=fulfillment (bucket full → não-ME1).
    Sem flag: base = produto_total = 26.99 → MC = 6.31.
    Com flag: base = vendas_aprovadas_linha = 45.98 → MC = 25.30.
    """
    orders = [
        {
            "order_id": 1, "status": "paid", "date_created": datetime(2026, 5, 26),
            "produto_total": Decimal("26.99"), "frete_comprador": Decimal("18.99"),
            "frete_vendedor": Decimal("6.55"), "tarifa_bruta": Decimal("3.24"),
            "tarifa_refund": Decimal("0"), "refund_amount_partial": Decimal("0"),
            "logistic_type": "fulfillment", "shipping_mode": "me2",
            "modalidade_anuncio": "gold_pro", "breakdown_bucket": "full",
        },
    ]
    items = [
        {"order_id": 1, "seller_sku": "577", "quantity": 1, "unit_price": Decimal("26.99"),
         "item_id": "MLB1", "title": "Retrovisor 577"},
    ]
    sku_financeiro = {
        "577": {"custo_unit": Decimal("8.46"), "imposto_pct": Decimal("9.00")},
    }

    result_sem = aggregate(orders, items, sku_financeiro, considerar_frete_comprador=False)
    result_com = aggregate(orders, items, sku_financeiro, considerar_frete_comprador=True)

    # Sem flag: base = produto_total → MC menor (frete_comprador subtraído)
    # Com flag: base = vendas_aprovadas_linha → MC maior (frete_comprador não subtraído)
    assert result_com["cards"]["mc_total"] > result_sem["cards"]["mc_total"]
    # Com flag: MC = (26.99+18.99) - 8.46 - (26.99*0.09) - 3.24 - 6.55 = 25.30
    assert result_com["cards"]["mc_total"] == Decimal("25.30")

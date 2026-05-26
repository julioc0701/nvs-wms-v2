from decimal import Decimal
from datetime import datetime
from services.ml_aggregator import compute_line_mc, aggregate


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
    assert cards["vendas_aprovadas"] == Decimal("45.98")     # só order 1
    assert cards["vendas_canceladas"] == Decimal("100.00")
    assert cards["faturamento_ml"] == Decimal("145.98")
    assert cards["qtd_vendas_aprovadas"] == 1
    assert cards["qtd_vendas_canceladas"] == 1

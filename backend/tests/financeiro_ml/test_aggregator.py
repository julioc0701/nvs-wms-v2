from decimal import Decimal
from services.ml_aggregator import compute_line_mc


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

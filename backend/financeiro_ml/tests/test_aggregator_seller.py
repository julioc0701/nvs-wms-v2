from decimal import Decimal
from datetime import datetime
from financeiro_ml.aggregator import aggregate


def _order(order_id, produto, status="paid"):
    return {"order_id": order_id, "status": status, "produto_total": Decimal(str(produto)),
            "frete_comprador": Decimal("0"), "frete_vendedor": Decimal("0"),
            "tarifa_bruta": Decimal("0"), "tarifa_refund": Decimal("0"),
            "refund_amount_partial": Decimal("0"), "cupom_seller": Decimal("0"),
            "logistic_type": None, "shipping_mode": None, "shipment_id": None,
            "breakdown_bucket": "outros", "date_created": datetime(2026,5,20)}


def test_aggregate_only_given_orders_counted():
    orders = [_order(1, 100), _order(2, 50)]
    items = [{"order_id": 1, "title": "A", "seller_sku": "X", "quantity": 1, "unit_price": Decimal("100")},
             {"order_id": 2, "title": "B", "seller_sku": "Y", "quantity": 1, "unit_price": Decimal("50")}]
    res = aggregate(orders, items, {})
    assert res["cards"]["vendas_aprovadas"] == Decimal("150.00")
    assert res["cards"]["qtd_vendas_aprovadas"] == 2

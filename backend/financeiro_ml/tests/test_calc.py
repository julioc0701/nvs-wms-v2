from decimal import Decimal
from financeiro_ml.calc import build_order_row


def _order(**over):
    base = {
        "id": 100,
        "status": "paid",
        "status_detail": None,
        "date_created": "2026-05-20T10:00:00.000-03:00",
        "date_closed": "2026-05-20T11:00:00.000-03:00",
        "date_last_updated": "2026-05-20T11:30:00.000-03:00",
        "tags": [],
        "order_items": [
            {"item": {"id": "MLB1", "title": "Prod A", "category_id": "CAT1",
                      "seller_custom_field": "SKU-A", "seller_sku": "SKU-A"},
             "unit_price": 50.0, "quantity": 2, "sale_fee": 5.0,
             "listing_type_id": "gold_pro"},
        ],
        "payments": [],
        "shipping": {"id": 9001},
    }
    base.update(over)
    return base


def test_build_row_basico_frete_vendedor_diff():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 20}, "logistic_type": "drop_off", "mode": "me2"}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert row["seller_id"] == 1
    assert row["order_id"] == 100
    assert row["produto_total"] == Decimal("100.0")    # 50 * 2
    assert row["tarifa_bruta"] == Decimal("10.0")      # 5 * 2
    assert row["frete_vendedor"] == Decimal("20")      # max(0, 20-0)
    assert row["frete_comprador"] == Decimal("0")
    assert row["breakdown_bucket"] == "places_coleta"


def test_build_row_items_list():
    order = _order()
    shipment = {"shipping_option": {"cost": 5, "list_cost": 5}}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert len(row["items"]) == 1
    assert row["items"][0]["seller_sku"] == "SKU-A"
    assert row["items"][0]["quantity"] == 2


def test_build_row_frete_loyal_mercado_pontos():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "fulfillment"}
    costs = {"receiver": {"save": 18.5, "discounts": [{"type": "loyal"}]},
             "senders": [{"cost": 0, "save": 0}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs=costs, discounts={"details": []})
    assert row["frete_comprador"] == Decimal("18.5")
    assert row["frete_incerto"] is False


def test_build_row_frete_ratio_flex():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "self_service"}
    costs = {"receiver": {"discounts": [{"type": "ratio"}]},
             "senders": [{"cost": 3.0, "save": 7.25}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs=costs, discounts={"details": []})
    assert row["frete_comprador"] == Decimal("7.25")


def test_build_row_frete_incerto_quando_costs_vazio():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "fulfillment"}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    # sem costs e fc=0 → marca incerteza (bug 4), não engole como 0 silencioso
    assert row["frete_incerto"] is True


def test_build_row_cupom_seller():
    order = _order(tags=["order_has_discount"])
    shipment = {"shipping_option": {"cost": 10, "list_cost": 10}}
    disc = {"details": [{"type": "coupon", "items": [{"amounts": {"seller": 12.0}}]}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts=disc)
    assert row["cupom_seller"] == Decimal("12.0")


def test_build_row_refund_parcial_e_cancel_zera():
    order = _order(payments=[{"transaction_amount_refunded": 30.0}])
    shipment = {"shipping_option": {"cost": 10, "list_cost": 10}}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert row["refund_amount_partial"] == Decimal("30.0")

    order_cancel = _order(status="cancelled", payments=[{"transaction_amount_refunded": 100.0}])
    row2 = build_order_row(seller_id=1, order=order_cancel, shipment=shipment,
                           shipment_costs={}, discounts={"details": []})
    assert row2["refund_amount_partial"] == Decimal("0")

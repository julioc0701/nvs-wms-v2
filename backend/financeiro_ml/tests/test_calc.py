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

import pytest


class FakeBillingClient:
    def __init__(self):
        self.calls = []

    async def get_billing_period_details(self, *, key, document_type, limit, from_id):
        self.calls.append((key, document_type, limit, from_id))
        if from_id == 0:
            return {
                "total": 3,
                "last_id": 20,
                "results": [
                    _line(10, order_id=1001, shipment_id=5001, amount=12.34),
                    _line(20, order_id=1002, shipment_id=5002, amount=9.87, as_lists=True),
                ],
            }
        return {
            "total": 1,
            "last_id": 30,
            "results": [
                _line(30, order_id=1003, shipment_id=5003, amount=1.23),
            ],
        }


def _line(detail_id, *, order_id, shipment_id, amount, as_lists=False):
    row = {
        "charge_info": {
            "detail_id": detail_id,
            "creation_date_time": "2026-06-01T10:00:00",
            "transaction_detail": "Tarifa de envio",
            "detail_amount": amount,
            "detail_type": "CHARGE",
            "detail_sub_type": "CXD",
        },
        "sales_info": {"order_id": order_id},
        "shipping_info": {"shipment_id": shipment_id},
        "marketplace_info": {"marketplace": "SHIPPING"},
    }
    if as_lists:
        row["sales_info"] = [row["sales_info"]]
        row["shipping_info"] = [row["shipping_info"]]
    return row


@pytest.mark.asyncio
async def test_billing_period_job_runs_with_checkpoint(fin_db):
    db, m = fin_db
    from financeiro_ml.billing_period import (
        create_billing_period_job,
        get_billing_period_job,
        run_billing_period_job,
    )

    job_id = create_billing_period_job(
        db.FinSessionLocal,
        seller_id=1,
        period_key="2026-06-01",
        limit=2,
    )

    client = FakeBillingClient()
    first = await run_billing_period_job(
        db.FinSessionLocal,
        client=client,
        job_id=job_id,
        max_pages=1,
    )

    assert first.status == "running"
    assert first.pages_processed == 1
    assert first.lines_processed == 2
    assert first.next_from_id == 20

    status = get_billing_period_job(db.FinSessionLocal, job_id)
    assert status["pages_done"] == 1
    assert status["lines_done"] == 2
    assert status["next_from_id"] == 20

    second = await run_billing_period_job(
        db.FinSessionLocal,
        client=client,
        job_id=job_id,
        max_pages=1,
    )

    assert second.status == "done"
    assert second.pages_processed == 1
    assert second.lines_processed == 1
    assert second.next_from_id == 30
    assert client.calls == [
        ("2026-06-01", "BILL", 2, 0),
        ("2026-06-01", "BILL", 2, 20),
    ]

    s = db.FinSessionLocal()
    try:
        lines = s.query(m.MLBillingPeriodLine).order_by(m.MLBillingPeriodLine.detail_id).all()
        assert [line.detail_id for line in lines] == [10, 20, 30]
        assert lines[0].order_id == 1001
        assert lines[0].shipment_id == 5001
        assert lines[1].order_id == 1002
        assert lines[1].shipment_id == 5002
    finally:
        s.close()

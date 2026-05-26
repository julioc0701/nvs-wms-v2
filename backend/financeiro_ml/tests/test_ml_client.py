import pytest
import httpx
import respx
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from financeiro_ml.client import MLClient


@pytest.mark.asyncio
@respx.mock
async def test_refresh_token_updates_db():
    """Quando access_token tá expirado, refresh é disparado antes da chamada."""

    # Mock do endpoint de refresh ML
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={
            "access_token": "novo_access_xyz",
            "refresh_token": "novo_refresh_abc",
            "expires_in": 21600,
            "user_id": 221832146,
        })
    )

    # Fake session com token expirado
    fake_session = MagicMock()
    fake_token_row = MagicMock(
        id=1,
        access_token="velho",
        refresh_token="refresh_velho",
        user_id=221832146,
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    fake_session.query.return_value.first.return_value = fake_token_row

    client = MLClient(session_factory=lambda: fake_session,
                       client_id="cid", client_secret="csec")
    new_token = await client._ensure_fresh_token()

    assert new_token == "novo_access_xyz"
    # Tabela foi atualizada
    assert fake_token_row.access_token == "novo_access_xyz"
    assert fake_token_row.refresh_token == "novo_refresh_abc"


@pytest.mark.asyncio
@respx.mock
async def test_get_retries_on_429():
    """Em 429 (rate limit), faz 2 retries com backoff e na 3ª passa."""

    route = respx.get("https://api.mercadolibre.com/orders/123").mock(side_effect=[
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(200, json={"id": 123, "status": "paid"}),
    ])

    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=1,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    result = await client._get("/orders/123")

    assert result["status"] == "paid"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_search_orders_passes_filters():
    respx.get("https://api.mercadolibre.com/orders/search").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1}], "paging": {"total": 1}})
    )
    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=221832146,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    result = await client.search_orders(
        date_from=datetime(2026, 5, 1),
        date_to=datetime(2026, 5, 2),
        offset=0, limit=50,
    )
    assert result["paging"]["total"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_order_returns_payload():
    respx.get("https://api.mercadolibre.com/orders/2000016614536174").mock(
        return_value=httpx.Response(200, json={"id": 2000016614536174, "status": "paid"})
    )
    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=1,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    result = await client.get_order(2000016614536174)
    assert result["id"] == 2000016614536174

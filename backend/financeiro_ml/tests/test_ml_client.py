import pytest
import httpx
import respx
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from financeiro_ml.client import MLClient, MLRateLimited


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
async def test_get_429_falha_rapido_sem_retry():
    """429 NÃO retenta (fail-fast): lança MLRateLimited na 1ª chamada."""

    route = respx.get("https://api.mercadolibre.com/orders/123").mock(
        return_value=httpx.Response(429)
    )

    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=1,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    with pytest.raises(MLRateLimited):
        await client._get("/orders/123")

    assert route.call_count == 1  # sem retry storm


@pytest.mark.asyncio
@respx.mock
async def test_get_404_falha_rapido_sem_retry():
    """4xx que não é 429 (ex 404) falha na hora, sem retentar."""

    route = respx.get("https://api.mercadolibre.com/orders/999").mock(
        return_value=httpx.Response(404)
    )

    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=1,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )

    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    with pytest.raises(httpx.HTTPStatusError):
        await client._get("/orders/999")

    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_5xx_retenta():
    """5xx (erro transitório do servidor) retenta e passa na 2ª."""

    route = respx.get("https://api.mercadolibre.com/orders/123").mock(side_effect=[
        httpx.Response(503),
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
    assert route.call_count == 2


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
async def test_search_orders_delta_usa_param_correto():
    """Delta DEVE usar order.date_last_updated.from (honrado pelo ML);
    order.last_updated.from é IGNORADO pelo ML (validado contra a API real)."""
    route = respx.get("https://api.mercadolibre.com/orders/search").mock(
        return_value=httpx.Response(200, json={"results": [], "paging": {"total": 0}})
    )
    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=221832146,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    await client.search_orders(
        date_from=datetime(2026, 5, 26), date_to=datetime(2026, 5, 26),
        last_updated_from=datetime(2026, 5, 28, 8, 0, 0),
    )
    url = str(route.calls.last.request.url)
    assert "order.date_last_updated.from" in url
    assert "order.last_updated.from" not in url.replace("order.date_last_updated.from", "")


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


@pytest.mark.asyncio
@respx.mock
async def test_get_variation_returns_payload():
    respx.get("https://api.mercadolibre.com/items/MLB123/variations/456").mock(
        return_value=httpx.Response(200, json={"id": 456, "seller_custom_field": "SKU_VARIACAO"})
    )
    fake_session = MagicMock()
    fake_session.query.return_value.first.return_value = MagicMock(
        access_token="ok", refresh_token="r", user_id=1,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = MLClient(session_factory=lambda: fake_session, client_id="x", client_secret="y")
    result = await client.get_variation("MLB123", 456)
    assert result["seller_custom_field"] == "SKU_VARIACAO"

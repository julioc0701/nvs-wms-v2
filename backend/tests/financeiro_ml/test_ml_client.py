import pytest
import httpx
import respx
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from services.ml_client import MLClient


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

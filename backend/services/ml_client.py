"""Cliente Mercado Livre async. OAuth + refresh + retry.

Inspirado no padrão do Devoluçao/app.py mas reescrito em httpx async.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Callable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ML_BASE = "https://api.mercadolibre.com"


class MLClient:
    def __init__(self, *, session_factory: Callable, client_id: str, client_secret: str,
                  timeout: float = 30.0):
        self._session_factory = session_factory
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

    async def _ensure_fresh_token(self) -> str:
        from models import MLTokens
        session = self._session_factory()
        try:
            token_row = session.query(MLTokens).first()
            if token_row is None:
                raise RuntimeError("ml_tokens vazio — configure variáveis ML_* no .env")

            # Renova se faltam menos de 60s pra expirar
            if token_row.expires_at - datetime.utcnow() > timedelta(seconds=60):
                return token_row.access_token

            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.post(
                    f"{ML_BASE}/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "refresh_token": token_row.refresh_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            token_row.access_token = data["access_token"]
            token_row.refresh_token = data["refresh_token"]
            token_row.expires_at = datetime.utcnow() + timedelta(seconds=int(data.get("expires_in", 21600)))
            token_row.updated_at = datetime.utcnow()
            session.commit()
            return token_row.access_token
        finally:
            session.close()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        token = await self._ensure_fresh_token()
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            resp = await http.get(
                f"{ML_BASE}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            # 429 e 5xx → retry; 4xx (exceto 429) → erro permanente
            if resp.status_code == 429 or resp.status_code >= 500:
                resp.raise_for_status()
            elif resp.status_code >= 400:
                resp.raise_for_status()
            return resp.json()

    async def get_order(self, order_id: int) -> dict:
        return await self._get(f"/orders/{order_id}")

    async def search_orders(self, *, date_from: datetime, date_to: datetime,
                             offset: int = 0, limit: int = 50) -> dict:
        from models import MLTokens
        session = self._session_factory()
        try:
            user_id = session.query(MLTokens).first().user_id
        finally:
            session.close()
        return await self._get("/orders/search", params={
            "seller": user_id,
            "order.date_created.from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "order.date_created.to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "offset": offset,
            "limit": limit,
        })

    async def get_shipment(self, shipment_id: int) -> dict:
        return await self._get(f"/shipments/{shipment_id}")

    async def get_item(self, item_id: str) -> dict:
        return await self._get(f"/items/{item_id}")


def build_default_client() -> MLClient:
    from database import SessionLocal
    return MLClient(
        session_factory=SessionLocal,
        client_id=os.getenv("ML_CLIENT_ID", ""),
        client_secret=os.getenv("ML_CLIENT_SECRET", ""),
    )

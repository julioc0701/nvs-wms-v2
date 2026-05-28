"""Cliente Mercado Livre async. OAuth + refresh + retry.

Inspirado no padrão do Devoluçao/app.py mas reescrito em httpx async.
"""
from __future__ import annotations

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Callable

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ML_BASE = "https://api.mercadolibre.com"
log = logging.getLogger("financeiro_ml.client")

# Throttle global: limita req/s ao ML pra não estourar rate limit (429).
# Default 0.2s entre chamadas = 5 req/s = 300/min. Ajustável via env.
_THROTTLE_INTERVAL = float(os.getenv("ML_THROTTLE_INTERVAL_SEC", "0.2"))
_throttle_lock = asyncio.Lock()
_throttle_last = 0.0


async def _global_throttle() -> None:
    """Garante intervalo mínimo entre chamadas ao ML (cross-coroutine)."""
    global _throttle_last
    async with _throttle_lock:
        loop = asyncio.get_event_loop()
        now = loop.time()
        wait = _THROTTLE_INTERVAL - (now - _throttle_last)
        if wait > 0:
            await asyncio.sleep(wait)
        _throttle_last = loop.time()


class MLClient:
    # Lock global (módulo-level): serializa refresh de token entre TODAS as instâncias
    # do MLClient. Evita race condition onde N coroutines paralelas usam o mesmo
    # refresh_token e ML invalida todos menos um → 401 cascade.
    _refresh_lock = asyncio.Lock()

    def __init__(self, *, session_factory: Callable, client_id: str, client_secret: str,
                  timeout: float = 30.0):
        self._session_factory = session_factory
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

    async def _ensure_fresh_token(self) -> str:
        from financeiro_ml.models import MLTokens
        # Fast path: leitura sem lock (a maioria das chamadas, token ainda fresh)
        session = self._session_factory()
        try:
            token_row = session.query(MLTokens).first()
            if token_row is None:
                raise RuntimeError("ml_tokens vazio — configure variáveis ML_* no .env")
            if token_row.expires_at - datetime.utcnow() > timedelta(seconds=60):
                return token_row.access_token
        finally:
            session.close()

        # Slow path: token precisa renovar. Serializa via lock.
        async with MLClient._refresh_lock:
            session = self._session_factory()
            try:
                token_row = session.query(MLTokens).first()
                # Re-check: outra coroutine pode ter renovado enquanto esperávamos
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
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        await _global_throttle()
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
        from financeiro_ml.models import MLTokens
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

    async def get_shipment_costs(self, shipment_id: int) -> dict:
        """GET /shipments/{id}/costs — detalhamento de custos do frete.

        Expõe `gross_amount`, `receiver.cost/save/discounts`, `senders[].cost`.
        Usado pra capturar subsídio Mercado Pontos (loyal) em vendas Flex,
        onde shipping_option.cost = 0 mas o comprador "viu" outro valor.
        """
        try:
            return await self._get(f"/shipments/{shipment_id}/costs")
        except Exception as exc:
            log.warning(
                "get_shipment_costs failed shipment_id=%s type=%s msg=%s",
                shipment_id, type(exc).__name__, str(exc)[:200],
            )
            return {}

    async def get_item(self, item_id: str) -> dict:
        return await self._get(f"/items/{item_id}")

    async def get_variation(self, item_id: str, variation_id: int | str) -> dict:
        return await self._get(f"/items/{item_id}/variations/{variation_id}")

    async def get_order_discounts(self, order_id: int) -> dict:
        """GET /orders/{id}/discounts — cupons e ofertas aplicadas.

        Retorna {details: [{type, items: [{amounts: {seller, total}}], supplier}]}.
        - type='coupon': cupom de campanha ML. Reduz o faturamento líquido do seller.
        - type='discount' + supplier.funding_mode='seller': offer promocional do
          seller (preço promocional já está em unit_price; não duplicar).
        Pedidos sem desconto retornam 404 — retornamos shape vazio.
        """
        try:
            return await self._get(f"/orders/{order_id}/discounts")
        except Exception as exc:
            log.warning(
                "get_order_discounts failed order_id=%s type=%s msg=%s",
                order_id, type(exc).__name__, str(exc)[:200],
            )
            return {"details": []}


def build_default_client() -> MLClient:
    from database import SessionLocal
    return MLClient(
        session_factory=SessionLocal,
        client_id=os.getenv("ML_CLIENT_ID", ""),
        client_secret=os.getenv("ML_CLIENT_SECRET", ""),
    )

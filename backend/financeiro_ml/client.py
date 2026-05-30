"""Cliente Mercado Livre async. OAuth + refresh + retry.

Inspirado no padrão do Devoluçao/app.py mas reescrito em httpx async.
"""
from __future__ import annotations

import asyncio
import os
import random
import logging
from datetime import datetime, timedelta
from typing import Callable

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception

ML_BASE = "https://api.mercadolibre.com"
log = logging.getLogger("financeiro_ml.client")


class MLRateLimited(Exception):
    """429 do ML. NÃO deve ser retentado em loop — sinaliza freio pro orquestrador.

    A doc do ML não expõe `Retry-After`; retentar em rajada só piora o rate limit
    (por Client ID + endpoint). Quem chama trata como circuit breaker: para, marca
    como pendente e tenta de novo mais tarde.
    """

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"429 Too Many Requests: {path}")


def _is_retryable(exc: BaseException) -> bool:
    """Só vale retentar timeout e 5xx (erro transitório do servidor).

    4xx (incl. 404/401/400) e 429 NÃO são retentáveis — falham na hora.
    """
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False

# Throttle global: limita req/s ao ML pra não estourar rate limit (429).
# Default 0.25s entre chamadas = 4 req/s = 240/min — margem abaixo do teto (~300/min
# por Client ID + endpoint). Ajustável via env.
_THROTTLE_INTERVAL = float(os.getenv("ML_THROTTLE_INTERVAL_SEC", "0.25"))

# Backoff exponencial + full jitter no 429 (SPEC §6). Re-tenta a MESMA chamada
# algumas vezes com espera crescente antes de desistir (lançar MLRateLimited).
# Não é o retry agressivo do incidente (tenacity 6x rápido) — é espaçado + jitter.
_R429_BASE_SEC = float(os.getenv("ML_429_BACKOFF_BASE_SEC", "2"))
_R429_CAP_SEC = float(os.getenv("ML_429_BACKOFF_CAP_SEC", "60"))
_R429_MAX_ATTEMPTS = int(os.getenv("ML_429_MAX_ATTEMPTS", "5"))
_throttle_lock = asyncio.Lock()
_throttle_last = 0.0

# Instrumentação Fase A: conta GETs ao ML por execução. Worker loga o delta/ciclo.
_ml_call_count = 0


def ml_call_count() -> int:
    return _ml_call_count


def _diag_429(resp) -> str:
    """Evidência diagnóstica de um 429: distingue rate-limit da API ML (corpo JSON
    tipo local_rate_limited) de bloqueio de borda/CDN (cf-ray, HTML). Defensivo —
    não quebra se a resposta não tiver headers/text (fakes de teste)."""
    try:
        h = getattr(resp, "headers", None) or {}
        keys = ("content-type", "retry-after", "cf-ray", "cf-mitigated", "server",
                "via", "x-cache", "x-ratelimit-limit", "x-ratelimit-remaining",
                "x-ratelimit-reset")
        diag = {k: h.get(k) for k in keys if hasattr(h, "get") and h.get(k)}
        body = (getattr(resp, "text", "") or "")[:500]
        return f"headers={diag} body={body!r}"
    except Exception as exc:
        return f"diag-indisponivel ({type(exc).__name__})"


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
    # Lock por seller: serializa refresh de token por seller_id. Refresh de A não
    # bloqueia B. Evita race onde N coroutines do mesmo seller usam o mesmo
    # refresh_token e o ML invalida todos menos um → 401 cascade.
    _refresh_locks: dict[int, asyncio.Lock] = {}

    @classmethod
    def _refresh_lock_for(cls, seller_id: int) -> asyncio.Lock:
        if seller_id not in cls._refresh_locks:
            cls._refresh_locks[seller_id] = asyncio.Lock()
        return cls._refresh_locks[seller_id]

    def __init__(self, *, session_factory: Callable, client_id: str, client_secret: str,
                  seller_id: int | None = None, timeout: float = 30.0):
        self._session_factory = session_factory
        self._client_id = client_id
        self._client_secret = client_secret
        self._seller_id = seller_id
        self._timeout = timeout

    async def _ensure_fresh_token(self) -> str:
        from financeiro_ml.models_v2 import MLTokens
        # Fast path: leitura sem lock (a maioria das chamadas, token ainda fresh)
        session = self._session_factory()
        try:
            token_row = session.query(MLTokens).filter_by(seller_id=self._seller_id).first()
            if token_row is None:
                raise RuntimeError("ml_tokens vazio — configure variáveis ML_* no .env")
            if token_row.expires_at - datetime.utcnow() > timedelta(seconds=60):
                return token_row.access_token
        finally:
            session.close()

        # Slow path: token precisa renovar. Serializa via lock por seller.
        async with MLClient._refresh_lock_for(self._seller_id):
            session = self._session_factory()
            try:
                token_row = session.query(MLTokens).filter_by(seller_id=self._seller_id).first()
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
        retry=retry_if_exception(_is_retryable),
        wait=wait_random_exponential(multiplier=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        attempt = 0
        while True:
            await _global_throttle()
            token = await self._ensure_fresh_token()
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.get(
                    f"{ML_BASE}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
            global _ml_call_count
            _ml_call_count += 1
            # 429 → backoff exponencial + full jitter; re-tenta a mesma chamada.
            # Esgotou as tentativas → lança MLRateLimited (orquestrador marca o dia).
            if resp.status_code == 429:
                attempt += 1
                # Instrumentação: captura corpo+headers do 429 (cota da API vs bloqueio de borda).
                log.warning("client.429 path=%s attempt=%s %s", path, attempt, _diag_429(resp))
                if attempt >= _R429_MAX_ATTEMPTS:
                    raise MLRateLimited(path)
                delay = random.uniform(0, min(_R429_CAP_SEC, _R429_BASE_SEC * (2 ** attempt)))
                await asyncio.sleep(delay)
                continue
            # 4xx não-429 → falha na hora (não retentável). 5xx → retenta (via _is_retryable).
            resp.raise_for_status()
            return resp.json()

    async def get_order(self, order_id: int) -> dict:
        return await self._get(f"/orders/{order_id}")

    async def search_orders(self, *, date_from: datetime, date_to: datetime,
                             offset: int = 0, limit: int = 50,
                             last_updated_from: datetime | None = None) -> dict:
        params = {
            "seller": self._seller_id,
            "order.date_created.from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "order.date_created.to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "offset": offset,
            "limit": limit,
        }
        # ATENÇÃO: filtro honrado pelo ML é `order.date_last_updated.from`
        # (`order.last_updated.from` é IGNORADO — validado contra a API real 2026-05-28).
        if last_updated_from is not None:
            params["order.date_last_updated.from"] = last_updated_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        return await self._get("/orders/search", params=params)

    async def scan_orders(self, *, date_from, date_to):
        """Gera orders via search_type=scan + scroll_id (sem teto de offset).
        Serial, concorrência=1. Não misturar com offset/limit."""
        params = {
            "seller": self._seller_id,
            "search_type": "scan",
            "order.date_created.from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "order.date_created.to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
        }
        scroll_id = None
        while True:
            if scroll_id:
                params["scroll_id"] = scroll_id
            page = await self._get("/orders/search", params=params)
            results = page.get("results", [])
            scroll_id = page.get("scroll_id")
            if not results:
                break
            for o in results:
                yield o
            if not scroll_id:
                break

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


def build_default_client(seller_id: int | None = None) -> MLClient:
    from financeiro_ml.db import FinSessionLocal
    return MLClient(
        session_factory=FinSessionLocal,
        client_id=os.getenv("ML_CLIENT_ID", ""),
        client_secret=os.getenv("ML_CLIENT_SECRET", ""),
        seller_id=seller_id,
    )

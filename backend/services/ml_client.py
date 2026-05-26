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


def build_default_client() -> MLClient:
    from database import SessionLocal
    return MLClient(
        session_factory=SessionLocal,
        client_id=os.getenv("ML_CLIENT_ID", ""),
        client_secret=os.getenv("ML_CLIENT_SECRET", ""),
    )

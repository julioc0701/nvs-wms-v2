# Mercado Turbo — Resumo Financeiro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replicar dentro do NVS-WMS o painel "Resumo Financeiro" do Mercado Turbo (Mercado Livre), eliminando dependência do SaaS pago.

**Architecture:** Módulo FastAPI isolado (`backend/financeiro_ml/` — router + 4 modules) com cliente Mercado Livre `httpx` async, cache local SQLite com política de freshness por dia, agregador pure-function. Frontend React com TanStack Query + Table + Recharts.

**Tech Stack:** Python 3.11 · FastAPI 0.115 · SQLAlchemy 2.0 · httpx 0.27 · tenacity (novo) · openpyxl · Pydantic. Frontend: React 18 · Vite · Tailwind · TanStack Query/Table v5 · Recharts · Radix Tooltip (todos novos no projeto).

**Spec de referência:** `docs/superpowers/specs/2026-05-26-mercado-turbo-resumo-financeiro-design.md`
**Estudo de referência:** `Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md`

---

## Estrutura de Arquivos

### Backend (a criar)
- `backend/financeiro_ml/client.py` — Cliente Mercado Livre async (httpx + OAuth refresh + retry).
- `backend/financeiro_ml/sync.py` — Orquestra sync por dia, política de freshness.
- `backend/financeiro_ml/aggregator.py` — Função pura: orders+items+skus → KPIs+pizza+tabela.
- `backend/financeiro_ml/sku_service.py` — CRUD do cadastro custo/imposto + import Excel.
- `backend/financeiro_ml/router.py` — Rotas REST `/api/financeiro-ml/*`.
- `backend/financeiro_ml/tests/__init__.py`
- `backend/financeiro_ml/tests/test_aggregator.py`
- `backend/financeiro_ml/tests/test_ml_client.py`
- `backend/financeiro_ml/tests/test_ml_sync.py`
- `backend/financeiro_ml/tests/test_sku_financeiro.py`
- `backend/financeiro_ml/tests/test_routers.py`
- `backend/financeiro_ml/tests/fixtures/ml_order_paid_full.json` (fixture de pedido real)
- `backend/financeiro_ml/tests/fixtures/ml_order_cancelled.json`
- `backend/financeiro_ml/tests/fixtures/ml_order_partial_refund.json`

### Backend (a modificar)
- `backend/requirements.txt` — adicionar `tenacity==9.0.0` e `respx==0.22.0` (dev).
- `backend/financeiro_ml/models.py` — 5 classes: `MLTokens`, `SkuFinanceiro`, `MLOrderCache`, `MLOrderItemCache`, `MLDaySyncStatus`.
- `backend/database.py` — `init_db()` cria as tabelas novas; migração inline pro seed inicial de `ml_tokens` a partir de env vars.
- `backend/main.py` — `app.include_router(financeiro_ml.router, prefix="/api/financeiro-ml", tags=["financeiro-ml"])`.

### Frontend (a criar)
- `frontend/src/lib/queryClient.js` — instância única do `QueryClient`.
- `frontend/src/financeiro-ml/api.js` — wrappers `fetch` por endpoint.
- `frontend/src/financeiro-ml/pages/Resumo.jsx`
- `frontend/src/financeiro-ml/pages/Skus.jsx`
- `frontend/src/financeiro-ml/components/KPICards.jsx`
- `frontend/src/financeiro-ml/components/PizzaChart.jsx`
- `frontend/src/financeiro-ml/components/FiltrosBar.jsx`
- `frontend/src/financeiro-ml/components/TabelaVendas.jsx`
- `frontend/src/financeiro-ml/components/SkuRow.jsx`
- `frontend/src/financeiro-ml/components/SkuImportDialog.jsx`
- `frontend/src/financeiro-ml/components/Tooltip.jsx` — wrapper do Radix.

### Frontend (a modificar)
- `frontend/package.json` — adicionar `recharts ^2.13.0`, `@tanstack/react-query ^5.59.0`, `@tanstack/react-table ^8.20.0`, `@radix-ui/react-tooltip ^1.1.2`.
- `frontend/src/main.jsx` — envolver app em `QueryClientProvider`.
- `frontend/src/App.jsx` — adicionar rotas `/financeiro-ml/resumo` e `/financeiro-ml/skus`.
- Layout/menu lateral (a localizar) — adicionar item "Financeiro ML" só pra Master.

### Docs/Env
- `.env.example` — adicionar variáveis ML (sample sem valores).

---

## Convenções para todas as tasks

- **TDD**: escrever teste antes do código (exceto onde marcado "no test — config only").
- **Run tests**: `cd backend && pytest tests/financeiro_ml/test_<file>.py -v` (backend) ou `cd frontend && npm test` (frontend, se houver Vitest configurado).
- **Commits**: convenção `feat(financeiro-ml): ...`, `test(financeiro-ml): ...`, `fix(financeiro-ml): ...`, `chore(financeiro-ml): ...`. Usar HEREDOC pra mensagem multilinha.
- **Não usar `git add .`** — sempre listar arquivos exatos por nome.
- **Não rodar deploy** (`publicar_producao.bat`) — só commits na branch atual.

---

# Backend

## Task 1: Adicionar dependências Python

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Adicionar tenacity e respx**

Abrir `backend/requirements.txt` e adicionar 2 linhas no final:

```
tenacity==9.0.0
respx==0.22.0
```

- [ ] **Step 2: Instalar localmente**

Run: `cd backend && pip install tenacity==9.0.0 respx==0.22.0`
Expected: dois pacotes instalados sem conflito.

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/requirements.txt
git commit -m "chore(financeiro-ml): add tenacity and respx for ML client"
```

---

## Task 2: Criar models SQLAlchemy

**Files:**
- Create: `backend/financeiro_ml/models.py`

- [ ] **Step 1: Adicionar imports no topo do arquivo**

Garantir que `financeiro_ml/models.py` tem na seção de imports:

```python
from sqlalchemy import Numeric, Date
```

(Os outros imports já existem — `Mapped`, `mapped_column`, `ForeignKey`, `String`, `Integer`, `DateTime`, `datetime`.)

- [ ] **Step 2: Adicionar 5 classes ao final do arquivo**

Acrescentar no final de `backend/models.py`:

```python
# ============================================================
# Financeiro ML — Mercado Livre (Resumo Financeiro)
# ============================================================

class MLTokens(Base):
    __tablename__ = "ml_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkuFinanceiro(Base):
    __tablename__ = "sku_financeiro"

    sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    custo_unit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    imposto_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)


class MLOrderCache(Base):
    __tablename__ = "ml_orders_cache"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_created: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    date_closed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    produto_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    frete_comprador: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    frete_vendedor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_bruta: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_refund: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    refund_amount_partial: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    modalidade_anuncio: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logistic_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    breakdown_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    synced_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MLOrderItemCache(Base):
    __tablename__ = "ml_order_items_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("ml_orders_cache.order_id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(30), nullable=True)


class MLDaySyncStatus(Base):
    __tablename__ = "ml_day_sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[datetime] = mapped_column(Date, nullable=False, unique=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

(`Text` deve ser importado em `financeiro_ml/models.py` — adicionar `Text` ao import de `sqlalchemy` se faltar.)

- [ ] **Step 3: Restartar app local pra `Base.metadata.create_all` rodar**

Run: `cd backend && python -c "from database import init_db; init_db()"`
Expected: sem erro. Banco `warehouse_v3_local.db` agora tem as 5 tabelas novas.

- [ ] **Step 4: Verificar tabelas criadas**

Run: `cd backend && python -c "import sqlite3; c=sqlite3.connect('warehouse_v3_local.db'); print(sorted([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]))"`
Expected: lista inclui `ml_day_sync_status`, `ml_order_items_cache`, `ml_orders_cache`, `ml_tokens`, `sku_financeiro`.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/models.py
git commit -m "feat(financeiro-ml): add 5 models for ML cache and SKU financeiro"
```

---

## Task 3: Seed inicial de `ml_tokens` a partir de env vars

**Files:**
- Modify: `backend/database.py` (dentro de `init_db()`)
- Modify: `.env.example`

- [ ] **Step 1: Adicionar bloco de seed em `database.py`**

Localizar a função `init_db()` em `backend/database.py`. Após a chamada de `Base.metadata.create_all(bind=engine)`, adicionar:

```python
    # Seed inicial de ml_tokens a partir do .env (rodada uma vez só)
    import os
    from models import MLTokens
    from datetime import datetime, timedelta
    with SessionLocal() as session:
        existing = session.query(MLTokens).first()
        if not existing:
            access = os.getenv("ML_ACCESS_TOKEN")
            refresh = os.getenv("ML_REFRESH_TOKEN")
            user_id = os.getenv("ML_USER_ID")
            if access and refresh and user_id:
                session.add(MLTokens(
                    id=1,
                    access_token=access,
                    refresh_token=refresh,
                    user_id=int(user_id),
                    expires_at=datetime.utcnow() + timedelta(hours=5),
                    updated_at=datetime.utcnow(),
                ))
                session.commit()
                print("[financeiro-ml] ml_tokens seeded from env")
```

- [ ] **Step 2: Adicionar variáveis no `.env.example`**

Abrir `.env.example` na raiz do projeto e acrescentar no final:

```
# Mercado Livre — Resumo Financeiro
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_REDIRECT_URI=
ML_USER_ID=
ML_ACCESS_TOKEN=
ML_REFRESH_TOKEN=
ML_SYNC_MAX_DAYS_PARALLEL=5
ML_SYNC_MAX_ORDERS_PARALLEL=10
```

- [ ] **Step 3: Testar seed manualmente (sem env válido)**

Run: `cd backend && python -c "from database import init_db; init_db()"`
Expected: sem erro mesmo sem `.env` setado (skip silencioso porque variáveis vazias).

- [ ] **Step 4: Commit**

```bash
git add backend/database.py .env.example
git commit -m "feat(financeiro-ml): seed ml_tokens from env on first init"
```

---

## Task 4: ML Client — estrutura básica e refresh token

**Files:**
- Create: `backend/financeiro_ml/client.py`
- Create: `backend/financeiro_ml/tests/__init__.py` (arquivo vazio)
- Create: `backend/financeiro_ml/tests/test_ml_client.py`

- [ ] **Step 1: Criar diretório de tests e arquivo vazio init**

Run: `mkdir -p backend/financeiro_ml/tests && touch backend/financeiro_ml/tests/__init__.py`

- [ ] **Step 2: Escrever teste de refresh token (que vai falhar)**

Criar `backend/financeiro_ml/tests/test_ml_client.py`:

```python
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
```

- [ ] **Step 3: Rodar teste — deve falhar com ImportError**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py -v`
Expected: ImportError "financeiro_ml.client" não existe.

- [ ] **Step 4: Criar `financeiro_ml/client.py`**

Criar arquivo:

```python
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
```

- [ ] **Step 5: Rodar teste novamente — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py::test_refresh_token_updates_db -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/__init__.py backend/financeiro_ml/tests/test_ml_client.py
git commit -m "feat(financeiro-ml): ML client skeleton with token refresh"
```

---

## Task 5: ML Client — método GET genérico com retry

**Files:**
- Modify: `backend/financeiro_ml/client.py`
- Modify: `backend/financeiro_ml/tests/test_ml_client.py`

- [ ] **Step 1: Escrever teste de retry em 429**

Adicionar ao `financeiro_ml/tests/test_ml_client.py`:

```python
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
```

- [ ] **Step 2: Rodar — deve falhar (método `_get` não existe)**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py::test_get_retries_on_429 -v`
Expected: AttributeError ou falha clara.

- [ ] **Step 3: Adicionar método `_get` em `financeiro_ml/client.py`**

Adicionar dentro da classe `MLClient`:

```python
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
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py::test_get_retries_on_429 -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/test_ml_client.py
git commit -m "feat(financeiro-ml): ML client _get with retry on 429/5xx"
```

---

## Task 6: ML Client — endpoints públicos

**Files:**
- Modify: `backend/financeiro_ml/client.py`
- Modify: `backend/financeiro_ml/tests/test_ml_client.py`

- [ ] **Step 1: Escrever teste dos 4 endpoints públicos**

Adicionar ao `financeiro_ml/tests/test_ml_client.py`:

```python
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
```

- [ ] **Step 2: Rodar — deve falhar (métodos não existem)**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py -v -k "search_orders or get_order_returns"`
Expected: AttributeError.

- [ ] **Step 3: Implementar 4 métodos públicos em `financeiro_ml/client.py`**

Adicionar dentro da classe `MLClient`:

```python
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
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_client.py -v`
Expected: 4 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/test_ml_client.py
git commit -m "feat(financeiro-ml): ML client public endpoints (search/get order/shipment/item)"
```

---

## Task 7: Aggregator — fórmula MC por linha

**Files:**
- Create: `backend/financeiro_ml/aggregator.py`
- Create: `backend/financeiro_ml/tests/test_aggregator.py`

- [ ] **Step 1: Escrever teste com a linha de validação do estudo**

Criar `backend/financeiro_ml/tests/test_aggregator.py`:

```python
from decimal import Decimal
from financeiro_ml.aggregator import compute_line_mc


def test_mc_line_full_modality_subtracts_buyer_freight():
    """Validação contra linha SKU 577 do print do MT.
    Valor unit 26,99 × 1, Frete Full (não ME1).
    Vendas Aprovadas (faturamento ML) = 45,98 (produto+frete_comprador).
    Custo 8,46; Imposto 2,43; Tarifa 3,24; Frete Comprador 18,99; Frete Vendedor 6,55.
    Resultado esperado: MC = 6,31; MC% = 23,38%.
    """
    result = compute_line_mc(
        produto_total=Decimal("26.99"),
        frete_comprador=Decimal("18.99"),
        frete_vendedor=Decimal("6.55"),
        custo=Decimal("8.46"),
        imposto=Decimal("2.43"),
        tarifa_liquida=Decimal("3.24"),
        refund_parcial=Decimal("0"),
        logistic_type="fulfillment",   # → bucket Full → não-ME1
        shipping_mode="me2",
    )
    assert result["mc"] == Decimal("6.31")
    assert result["mc_pct"] == Decimal("23.38")


def test_mc_line_me1_keeps_buyer_freight():
    """Em ME1 o frete comprador NÃO é subtraído."""
    result = compute_line_mc(
        produto_total=Decimal("26.99"),
        frete_comprador=Decimal("18.99"),
        frete_vendedor=Decimal("6.55"),
        custo=Decimal("8.46"),
        imposto=Decimal("2.43"),
        tarifa_liquida=Decimal("3.24"),
        refund_parcial=Decimal("0"),
        logistic_type=None,
        shipping_mode="me1",
    )
    # MC = (26.99+18.99) - 8.46 - 2.43 - 3.24 - 6.55 = 25.30
    assert result["mc"] == Decimal("25.30")
```

- [ ] **Step 2: Rodar — deve falhar (módulo não existe)**

Run: `cd backend && pytest financeiro_ml/tests/test_aggregator.py -v`
Expected: ImportError.

- [ ] **Step 3: Criar `financeiro_ml/aggregator.py`**

```python
"""Agregador puro. Sem I/O. Recebe dados, devolve KPIs e tabela.

Implementa as fórmulas validadas em Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md §3.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

ME1_OR_OUTROS_BUCKETS = {"me1", "outros"}


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_line_mc(*, produto_total: Decimal, frete_comprador: Decimal,
                     frete_vendedor: Decimal, custo: Decimal, imposto: Decimal,
                     tarifa_liquida: Decimal, refund_parcial: Decimal,
                     logistic_type: str | None, shipping_mode: str | None) -> dict:
    """Calcula MC e MC% pra uma linha de venda.

    Regra: frete_comprador é subtraído da base salvo quando modalidade é ME1
    ou "Outro (a combinar)" — nestes casos o vendedor absorve o frete.
    """
    bucket = _logistic_bucket(logistic_type, shipping_mode)
    keeps_buyer_freight = bucket in ME1_OR_OUTROS_BUCKETS

    vendas_aprovadas_linha = produto_total + frete_comprador  # = Faturamento ML linha

    if keeps_buyer_freight:
        base = vendas_aprovadas_linha
    else:
        base = produto_total

    mc = base - custo - imposto - tarifa_liquida - frete_vendedor - refund_parcial
    mc_pct = (mc / produto_total * Decimal("100")) if produto_total > 0 else Decimal("0")

    return {
        "mc": _q(mc),
        "mc_pct": _q(mc_pct),
        "vendas_aprovadas_linha": _q(vendas_aprovadas_linha),
    }


def _logistic_bucket(logistic_type: str | None, shipping_mode: str | None) -> str:
    """Mapeia campos ML pra bucket do breakdown logístico.

    Mapping inicial — refinar quando testes ML revelarem combinações reais.
    """
    if shipping_mode == "me1":
        return "me1"
    if logistic_type == "fulfillment":
        return "full"
    if logistic_type == "self_service":
        return "flex"
    if logistic_type in ("drop_off", "cross_docking"):
        return "places_coleta"
    return "outros"
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_aggregator.py -v`
Expected: 2 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/aggregator.py backend/financeiro_ml/tests/test_aggregator.py
git commit -m "feat(financeiro-ml): aggregator with MC per-line formula (validated against MT screenshot)"
```

---

## Task 8: Aggregator — agregação global (cards + pizza + tabela)

**Files:**
- Modify: `backend/financeiro_ml/aggregator.py`
- Modify: `backend/financeiro_ml/tests/test_aggregator.py`

- [ ] **Step 1: Escrever teste do agregador global com 2 linhas**

Adicionar ao `financeiro_ml/tests/test_aggregator.py`:

```python
from datetime import datetime
from financeiro_ml.aggregator import aggregate


def test_aggregate_two_orders_one_approved_one_cancelled():
    orders = [
        {
            "order_id": 1, "status": "paid", "date_created": datetime(2026, 5, 26),
            "produto_total": Decimal("26.99"), "frete_comprador": Decimal("18.99"),
            "frete_vendedor": Decimal("6.55"), "tarifa_bruta": Decimal("3.24"),
            "tarifa_refund": Decimal("0"), "refund_amount_partial": Decimal("0"),
            "logistic_type": "fulfillment", "shipping_mode": "me2",
            "modalidade_anuncio": "gold_pro", "breakdown_bucket": "full",
        },
        {
            "order_id": 2, "status": "cancelled", "date_created": datetime(2026, 5, 26),
            "produto_total": Decimal("100.00"), "frete_comprador": Decimal("0"),
            "frete_vendedor": Decimal("0"), "tarifa_bruta": Decimal("0"),
            "tarifa_refund": Decimal("0"), "refund_amount_partial": Decimal("0"),
            "logistic_type": "fulfillment", "shipping_mode": "me2",
            "modalidade_anuncio": "gold_pro", "breakdown_bucket": "full",
        },
    ]
    items = [
        {"order_id": 1, "seller_sku": "577", "quantity": 1, "unit_price": Decimal("26.99"),
         "item_id": "MLB1", "title": "Retrovisor 577"},
        {"order_id": 2, "seller_sku": "999", "quantity": 1, "unit_price": Decimal("100.00"),
         "item_id": "MLB2", "title": "Outro"},
    ]
    sku_financeiro = {
        "577": {"custo_unit": Decimal("8.46"), "imposto_pct": Decimal("9.00")},
        "999": {"custo_unit": Decimal("50.00"), "imposto_pct": Decimal("9.00")},
    }
    result = aggregate(orders, items, sku_financeiro)
    cards = result["cards"]
    assert cards["vendas_aprovadas"] == Decimal("45.98")     # só order 1
    assert cards["vendas_canceladas"] == Decimal("100.00")
    assert cards["faturamento_ml"] == Decimal("145.98")
    assert cards["qtd_vendas_aprovadas"] == 1
    assert cards["qtd_vendas_canceladas"] == 1
```

- [ ] **Step 2: Rodar — deve falhar (`aggregate` não existe)**

Run: `cd backend && pytest financeiro_ml/tests/test_aggregator.py::test_aggregate_two_orders_one_approved_one_cancelled -v`
Expected: ImportError.

- [ ] **Step 3: Implementar `aggregate()` em `financeiro_ml/aggregator.py`**

Adicionar ao final do arquivo:

```python
from collections import defaultdict


def aggregate(orders: list[dict], items: list[dict], sku_financeiro: dict[str, dict]) -> dict:
    """Agrega lista de orders + itens + cadastro SKU em KPIs prontos.

    Retorna: {cards, pizza, tabela}.
    """
    items_by_order: dict[int, list[dict]] = defaultdict(list)
    for it in items:
        items_by_order[it["order_id"]].append(it)

    tabela_linhas = []
    sum_aprovadas = Decimal("0")
    sum_canceladas = Decimal("0")
    sum_custo = Decimal("0")
    sum_imposto = Decimal("0")
    sum_tarifa = Decimal("0")
    sum_frete_comprador = Decimal("0")
    sum_frete_vendedor = Decimal("0")
    sum_refund_partial = Decimal("0")
    sum_mc = Decimal("0")
    qtd_aprovadas = 0
    qtd_canceladas = 0
    units_aprovadas = 0
    units_canceladas = 0
    buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for order in orders:
        order_items = items_by_order.get(order["order_id"], [])
        is_aprovada = order["status"] == "paid"
        is_cancelada = order["status"] == "cancelled"

        # Custo e imposto agregados de todos os itens do pedido
        custo_order = Decimal("0")
        imposto_order = Decimal("0")
        unidades = 0
        for it in order_items:
            sku = (it.get("seller_sku") or "").strip()
            fin = sku_financeiro.get(sku, {"custo_unit": Decimal("0"), "imposto_pct": Decimal("0")})
            custo_order += fin["custo_unit"] * Decimal(it["quantity"])
            unidades += it["quantity"]
        # Imposto incide sobre o produto puro do pedido
        # Se vários itens com aliquota diferente, simplifica: aliquota = média ponderada pelo valor
        if order["produto_total"] > 0:
            imposto_sum_weighted = Decimal("0")
            for it in order_items:
                sku = (it.get("seller_sku") or "").strip()
                fin = sku_financeiro.get(sku, {"imposto_pct": Decimal("0")})
                linha_valor = it["unit_price"] * Decimal(it["quantity"])
                imposto_sum_weighted += linha_valor * fin["imposto_pct"] / Decimal("100")
            imposto_order = imposto_sum_weighted

        tarifa_liquida = order["tarifa_bruta"] - order["tarifa_refund"]

        line_mc = compute_line_mc(
            produto_total=order["produto_total"],
            frete_comprador=order["frete_comprador"],
            frete_vendedor=order["frete_vendedor"],
            custo=custo_order,
            imposto=imposto_order,
            tarifa_liquida=tarifa_liquida,
            refund_parcial=order["refund_amount_partial"],
            logistic_type=order.get("logistic_type"),
            shipping_mode=order.get("shipping_mode"),
        )

        # Para tabela: 1 linha por item (igual MT)
        for it in order_items:
            tabela_linhas.append({
                "order_id": order["order_id"],
                "anuncio": it["title"],
                "sku": it.get("seller_sku") or "",
                "data": order["date_created"].isoformat(),
                "frete_label": order.get("breakdown_bucket", "outros"),
                "valor_unit": _q(it["unit_price"]),
                "qty": it["quantity"],
                "faturamento_ml": line_mc["vendas_aprovadas_linha"],
                "custo": _q(custo_order * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "imposto": _q(imposto_order * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "tarifa": _q(tarifa_liquida * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "frete_comprador": _q(order["frete_comprador"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "frete_vendedor": _q(order["frete_vendedor"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "mc": _q(line_mc["mc"] * Decimal(it["quantity"]) / Decimal(max(unidades, 1))),
                "mc_pct": line_mc["mc_pct"],
            })

        if is_aprovada:
            sum_aprovadas += line_mc["vendas_aprovadas_linha"]
            sum_custo += custo_order
            sum_imposto += imposto_order
            sum_tarifa += tarifa_liquida
            sum_frete_comprador += order["frete_comprador"]
            sum_frete_vendedor += order["frete_vendedor"]
            sum_refund_partial += order["refund_amount_partial"]
            sum_mc += line_mc["mc"]
            qtd_aprovadas += 1
            units_aprovadas += unidades
            buckets[order.get("breakdown_bucket", "outros")] += line_mc["vendas_aprovadas_linha"]
        elif is_cancelada:
            sum_canceladas += line_mc["vendas_aprovadas_linha"]
            qtd_canceladas += 1
            units_canceladas += unidades

    faturamento_ml = sum_aprovadas + sum_canceladas
    ticket_medio = (sum_aprovadas / qtd_aprovadas) if qtd_aprovadas else Decimal("0")
    ticket_mc = (sum_mc / qtd_aprovadas) if qtd_aprovadas else Decimal("0")
    mc_pct_global = (sum_mc / sum_aprovadas * Decimal("100")) if sum_aprovadas else Decimal("0")

    cards = {
        "vendas_aprovadas": _q(sum_aprovadas),
        "vendas_canceladas": _q(sum_canceladas),
        "faturamento_ml": _q(faturamento_ml),
        "custo_total": _q(sum_custo),
        "imposto_total": _q(sum_imposto),
        "custo_imposto_total": _q(sum_custo + sum_imposto),
        "tarifa_venda": _q(sum_tarifa),
        "frete_comprador_total": _q(sum_frete_comprador),
        "frete_vendedor_total": _q(sum_frete_vendedor),
        "frete_total": _q(sum_frete_comprador + sum_frete_vendedor),
        "mc_total": _q(sum_mc),
        "mc_pct_global": _q(mc_pct_global),
        "ticket_medio": _q(ticket_medio),
        "ticket_mc": _q(ticket_mc),
        "qtd_vendas_aprovadas": qtd_aprovadas,
        "qtd_vendas_canceladas": qtd_canceladas,
        "qtd_total_vendas": qtd_aprovadas + qtd_canceladas,
        "unidades_aprovadas": units_aprovadas,
        "unidades_canceladas": units_canceladas,
        "devolucoes_parciais_valor": _q(sum_refund_partial),
        "breakdown_logistico": {k: _q(v) for k, v in buckets.items()},
    }

    base_pizza = sum_aprovadas
    pizza = []
    if base_pizza > 0:
        pizza = [
            {"label": "Custo", "valor": _q(sum_custo), "pct": _q(sum_custo / base_pizza * Decimal("100"))},
            {"label": "Imposto", "valor": _q(sum_imposto), "pct": _q(sum_imposto / base_pizza * Decimal("100"))},
            {"label": "Tarifa", "valor": _q(sum_tarifa), "pct": _q(sum_tarifa / base_pizza * Decimal("100"))},
            {"label": "Frete", "valor": _q(sum_frete_vendedor), "pct": _q(sum_frete_vendedor / base_pizza * Decimal("100"))},
            {"label": "MC", "valor": _q(sum_mc), "pct": _q(mc_pct_global)},
        ]

    return {
        "cards": cards,
        "pizza": pizza,
        "tabela": tabela_linhas,
    }
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_aggregator.py -v`
Expected: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/aggregator.py backend/financeiro_ml/tests/test_aggregator.py
git commit -m "feat(financeiro-ml): aggregator with global KPIs and pizza"
```

---

## Task 9: SKU Financeiro service — CRUD

**Files:**
- Create: `backend/financeiro_ml/sku_service.py`
- Create: `backend/financeiro_ml/tests/test_sku_financeiro.py`

- [ ] **Step 1: Escrever testes do CRUD**

Criar `backend/financeiro_ml/tests/test_sku_financeiro.py`:

```python
import pytest
from decimal import Decimal
from database import SessionLocal, init_db
from models import SkuFinanceiro, Operator
from financeiro_ml.sku_service import upsert_sku, list_skus, delete_sku


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        # Garante operator 1 existe
        if not s.query(Operator).filter_by(id=1).first():
            s.add(Operator(id=1, name="Test", badge="T", pin_code="1234"))
            s.commit()
        # Limpa skus pra isolar
        s.query(SkuFinanceiro).delete()
        s.commit()


def test_upsert_creates_new_sku():
    upsert_sku("SKU_NEW", custo_unit=Decimal("10.00"), imposto_pct=Decimal("8.50"), updated_by_id=1)
    with SessionLocal() as s:
        row = s.query(SkuFinanceiro).filter_by(sku="SKU_NEW").first()
        assert row is not None
        assert row.custo_unit == Decimal("10.00")


def test_upsert_updates_existing():
    upsert_sku("SKU_X", custo_unit=Decimal("5"), imposto_pct=Decimal("8"), updated_by_id=1)
    upsert_sku("SKU_X", custo_unit=Decimal("99"), imposto_pct=Decimal("10"), updated_by_id=1)
    with SessionLocal() as s:
        row = s.query(SkuFinanceiro).filter_by(sku="SKU_X").first()
        assert row.custo_unit == Decimal("99")
        assert row.imposto_pct == Decimal("10")


def test_list_skus_returns_dict():
    upsert_sku("SKU_A", custo_unit=Decimal("1"), imposto_pct=Decimal("9"), updated_by_id=1)
    upsert_sku("SKU_B", custo_unit=Decimal("2"), imposto_pct=Decimal("9"), updated_by_id=1)
    result = list_skus()
    assert "SKU_A" in result
    assert result["SKU_A"]["custo_unit"] == Decimal("1")


def test_delete_sku():
    upsert_sku("SKU_DEL", custo_unit=Decimal("1"), imposto_pct=Decimal("9"), updated_by_id=1)
    delete_sku("SKU_DEL")
    with SessionLocal() as s:
        assert s.query(SkuFinanceiro).filter_by(sku="SKU_DEL").first() is None
```

- [ ] **Step 2: Rodar — deve falhar (módulo não existe)**

Run: `cd backend && pytest financeiro_ml/tests/test_sku_financeiro.py -v`
Expected: ImportError.

- [ ] **Step 3: Implementar service**

Criar `backend/financeiro_ml/sku_service.py`:

```python
"""CRUD da tabela sku_financeiro + import Excel."""
from decimal import Decimal
from datetime import datetime

from database import SessionLocal
from models import SkuFinanceiro


def upsert_sku(sku: str, *, custo_unit: Decimal, imposto_pct: Decimal, updated_by_id: int) -> None:
    with SessionLocal() as session:
        row = session.query(SkuFinanceiro).filter_by(sku=sku).first()
        if row is None:
            row = SkuFinanceiro(sku=sku, custo_unit=custo_unit, imposto_pct=imposto_pct,
                                  updated_by=updated_by_id, updated_at=datetime.utcnow())
            session.add(row)
        else:
            row.custo_unit = custo_unit
            row.imposto_pct = imposto_pct
            row.updated_by = updated_by_id
            row.updated_at = datetime.utcnow()
        session.commit()


def list_skus(query: str | None = None) -> dict[str, dict]:
    with SessionLocal() as session:
        q = session.query(SkuFinanceiro)
        if query:
            q = q.filter(SkuFinanceiro.sku.like(f"%{query}%"))
        return {
            row.sku: {
                "custo_unit": row.custo_unit,
                "imposto_pct": row.imposto_pct,
                "updated_at": row.updated_at,
            }
            for row in q.all()
        }


def delete_sku(sku: str) -> bool:
    with SessionLocal() as session:
        row = session.query(SkuFinanceiro).filter_by(sku=sku).first()
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_sku_financeiro.py -v`
Expected: 4 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/sku_service.py backend/financeiro_ml/tests/test_sku_financeiro.py
git commit -m "feat(financeiro-ml): sku_financeiro CRUD service"
```

---

## Task 10: SKU Financeiro service — import Excel

**Files:**
- Modify: `backend/financeiro_ml/sku_service.py`
- Modify: `backend/financeiro_ml/tests/test_sku_financeiro.py`

- [ ] **Step 1: Escrever teste do import**

Adicionar ao `financeiro_ml/tests/test_sku_financeiro.py`:

```python
import io
from openpyxl import Workbook
from financeiro_ml.sku_service import import_excel


def test_import_excel_creates_and_updates():
    # Prepara um xlsx fake com colunas sku, custo_unit, imposto_pct
    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "custo_unit", "imposto_pct"])
    ws.append(["IMP_A", 12.5, 8.0])
    ws.append(["IMP_B", 20.0, 9.5])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    result = import_excel(buf, updated_by_id=1)
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["errors"] == []

    # Reimport mesma planilha
    buf.seek(0)
    result2 = import_excel(buf, updated_by_id=1)
    assert result2["created"] == 0
    assert result2["updated"] == 2
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd backend && pytest financeiro_ml/tests/test_sku_financeiro.py::test_import_excel_creates_and_updates -v`
Expected: ImportError.

- [ ] **Step 3: Implementar `import_excel`**

Adicionar ao final de `financeiro_ml/sku_service.py`:

```python
from openpyxl import load_workbook
from typing import BinaryIO


def import_excel(file: BinaryIO, *, updated_by_id: int) -> dict:
    """Importa planilha com colunas: sku, custo_unit, imposto_pct.
    Aceita ordem qualquer das colunas (lê pelo header).
    Retorna {created, updated, errors: list[{linha, motivo}]}.
    """
    wb = load_workbook(file, data_only=True, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return {"created": 0, "updated": 0, "errors": [{"linha": 0, "motivo": "planilha vazia"}]}

    header = {str(c).strip().lower(): i for i, c in enumerate(rows[0]) if c is not None}
    required = ("sku", "custo_unit", "imposto_pct")
    missing = [h for h in required if h not in header]
    if missing:
        return {"created": 0, "updated": 0, "errors": [{"linha": 1, "motivo": f"colunas faltando: {missing}"}]}

    existing = set(list_skus().keys())
    created = 0
    updated = 0
    errors = []

    for line_no, row in enumerate(rows[1:], start=2):
        try:
            sku = str(row[header["sku"]]).strip() if row[header["sku"]] is not None else ""
            if not sku:
                errors.append({"linha": line_no, "motivo": "sku vazio"})
                continue
            custo = Decimal(str(row[header["custo_unit"]] or "0"))
            imposto = Decimal(str(row[header["imposto_pct"]] or "0"))
            upsert_sku(sku, custo_unit=custo, imposto_pct=imposto, updated_by_id=updated_by_id)
            if sku in existing:
                updated += 1
            else:
                created += 1
                existing.add(sku)
        except Exception as e:
            errors.append({"linha": line_no, "motivo": str(e)})

    return {"created": created, "updated": updated, "errors": errors}
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_sku_financeiro.py -v`
Expected: 5 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/sku_service.py backend/financeiro_ml/tests/test_sku_financeiro.py
git commit -m "feat(financeiro-ml): excel import for sku_financeiro"
```

---

## Task 11: Sync service — política de freshness

**Files:**
- Create: `backend/financeiro_ml/sync.py`
- Create: `backend/financeiro_ml/tests/test_ml_sync.py`

- [ ] **Step 1: Escrever teste da função `_days_needing_sync`**

Criar `backend/financeiro_ml/tests/test_ml_sync.py`:

```python
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from financeiro_ml.sync import _days_needing_sync, _date_range


def test_date_range_inclusive():
    days = _date_range(date(2026, 5, 1), date(2026, 5, 3))
    assert days == [date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)]


def test_today_always_needs_sync():
    today = date.today()
    statuses = {today: MagicMock(last_synced_at=datetime.utcnow() - timedelta(minutes=1), status="ok")}
    result = _days_needing_sync([today], statuses)
    assert result == [today]


def test_old_day_not_needed_if_ok():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="ok")}
    result = _days_needing_sync([old], statuses)
    assert result == []


def test_old_day_failed_needs_retry():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="failed")}
    result = _days_needing_sync([old], statuses)
    assert result == [old]


def test_recent_day_stale_24h_needs_sync():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=25), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == [recent]


def test_recent_day_fresh_skipped():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=5), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == []


def test_missing_day_needs_sync():
    target = date.today() - timedelta(days=2)
    result = _days_needing_sync([target], {})
    assert result == [target]
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_sync.py -v`
Expected: ImportError.

- [ ] **Step 3: Criar `financeiro_ml/sync.py`**

```python
"""Sincronização de cache ML por dia. Política de freshness."""
from datetime import date, datetime, timedelta


def _date_range(start: date, end: date) -> list[date]:
    """Lista inclusiva de datas entre start e end."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _days_needing_sync(days: list[date], statuses: dict[date, object]) -> list[date]:
    """Aplica política de freshness e retorna apenas os dias que precisam re-sync.

    Regras:
    - day == today → sempre.
    - day in [today-7, today-1] e last_synced_at > 24h → sim.
    - day < today-7 e status == 'ok' → não.
    - day < today-7 e status == 'failed' → sim.
    - day sem status → sim.
    """
    today = date.today()
    threshold_recent = today - timedelta(days=7)
    now = datetime.utcnow()
    needed = []
    for d in days:
        if d == today:
            needed.append(d)
            continue
        st = statuses.get(d)
        if st is None:
            needed.append(d)
            continue
        if st.status == "failed":
            needed.append(d)
            continue
        if d >= threshold_recent:
            if now - st.last_synced_at > timedelta(hours=24):
                needed.append(d)
    return needed
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_ml_sync.py -v`
Expected: 7 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/sync.py backend/financeiro_ml/tests/test_ml_sync.py
git commit -m "feat(financeiro-ml): sync service freshness policy"
```

---

## Task 12: Sync service — função orquestradora `ensure_period_synced`

**Files:**
- Modify: `backend/financeiro_ml/sync.py`

> Por simplicidade, esta tarefa NÃO escreve testes unitários do orquestrador
> (mocking de async + DB + ML é pesado). O teste real fica em smoke manual (Task 23).
> O fluxo é só "cola" de funções já testadas individualmente.

- [ ] **Step 1: Implementar `ensure_period_synced`**

Adicionar ao final de `services/ml_sync.py`:

```python
import asyncio
import json
import os
from decimal import Decimal

from database import SessionLocal
from models import MLDaySyncStatus, MLOrderCache, MLOrderItemCache
from financeiro_ml.client import build_default_client


async def ensure_period_synced(date_from: date, date_to: date) -> dict:
    """Orquestra sync por dia. Retorna {dias_sincronizados, dias_falhos, total_orders}."""
    days = _date_range(date_from, date_to)

    with SessionLocal() as session:
        statuses_rows = session.query(MLDaySyncStatus).filter(
            MLDaySyncStatus.day.in_(days)
        ).all()
        statuses = {s.day: s for s in statuses_rows}

    needed = _days_needing_sync(days, statuses)
    if not needed:
        return {"dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0}

    max_parallel = int(os.getenv("ML_SYNC_MAX_DAYS_PARALLEL", "5"))
    sem = asyncio.Semaphore(max_parallel)
    client = build_default_client()

    async def sync_one(d: date):
        async with sem:
            return await _sync_single_day(client, d)

    results = await asyncio.gather(*[sync_one(d) for d in needed], return_exceptions=True)
    sucessos = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "ok")
    falhas = len(results) - sucessos
    total = sum(r.get("orders_count", 0) for r in results if isinstance(r, dict))
    return {"dias_sincronizados": sucessos, "dias_falhos": falhas, "total_orders": total}


async def _sync_single_day(client, d: date) -> dict:
    """Sincroniza um dia: busca orders, detalha cada um, insere no cache."""
    inicio = datetime(d.year, d.month, d.day, 0, 0, 0)
    fim = datetime(d.year, d.month, d.day, 23, 59, 59)
    orders_count = 0
    try:
        offset = 0
        while True:
            page = await client.search_orders(date_from=inicio, date_to=fim, offset=offset, limit=50)
            results = page.get("results", [])
            if not results:
                break
            for order in results:
                await _save_order(client, order)
                orders_count += 1
            if len(results) < 50:
                break
            offset += 50

        with SessionLocal() as session:
            st = session.query(MLDaySyncStatus).filter_by(day=d).first()
            if st is None:
                st = MLDaySyncStatus(day=d, last_synced_at=datetime.utcnow(),
                                       orders_count=orders_count, status="ok")
                session.add(st)
            else:
                st.last_synced_at = datetime.utcnow()
                st.orders_count = orders_count
                st.status = "ok"
                st.error_message = None
            session.commit()
        return {"status": "ok", "orders_count": orders_count}
    except Exception as e:
        with SessionLocal() as session:
            st = session.query(MLDaySyncStatus).filter_by(day=d).first()
            if st is None:
                st = MLDaySyncStatus(day=d, last_synced_at=datetime.utcnow(),
                                       orders_count=0, status="failed", error_message=str(e))
                session.add(st)
            else:
                st.last_synced_at = datetime.utcnow()
                st.status = "failed"
                st.error_message = str(e)
            session.commit()
        return {"status": "failed", "orders_count": 0, "error": str(e)}


async def _save_order(client, search_result: dict) -> None:
    """Detalha um order do search result e salva no cache (upsert)."""
    order_id = search_result["id"]
    detail = await client.get_order(order_id)

    shipment_id = (detail.get("shipping") or {}).get("id")
    shipment = await client.get_shipment(shipment_id) if shipment_id else {}

    # Calcula totais
    produto_total = Decimal("0")
    tarifa_bruta = Decimal("0")
    for it in detail.get("order_items", []):
        produto_total += Decimal(str(it["unit_price"])) * Decimal(it["quantity"])
        tarifa_bruta += Decimal(str(it.get("sale_fee", 0))) * Decimal(it["quantity"])

    frete_comprador = Decimal(str((shipment.get("shipping_option") or {}).get("cost", 0) or 0))
    frete_vendedor = Decimal(str((shipment.get("shipping_option") or {}).get("list_cost", 0) or 0))

    refund_total = Decimal("0")
    for refund in (detail.get("payments") or []):
        refund_total += Decimal(str(refund.get("transaction_amount_refunded", 0) or 0))

    is_total_cancel = detail.get("status") == "cancelled"
    refund_partial = Decimal("0") if is_total_cancel else refund_total

    logistic_type = shipment.get("logistic_type")
    shipping_mode = shipment.get("mode")

    # Bucket pra breakdown logístico
    from financeiro_ml.aggregator import _logistic_bucket
    bucket = _logistic_bucket(logistic_type, shipping_mode)

    # Modalidade do anúncio (precisa do listing_type_id) — pega do primeiro item
    modalidade = None
    first_item = (detail.get("order_items") or [{}])[0].get("item", {})
    item_id = first_item.get("id")
    if item_id:
        try:
            item_detail = await client.get_item(item_id)
            modalidade = item_detail.get("listing_type_id")
        except Exception:
            pass

    with SessionLocal() as session:
        existing = session.query(MLOrderCache).filter_by(order_id=order_id).first()
        if existing is None:
            row = MLOrderCache(
                order_id=order_id,
                date_created=datetime.fromisoformat(detail["date_created"].replace("Z", "+00:00")),
                date_closed=(datetime.fromisoformat(detail["date_closed"].replace("Z", "+00:00"))
                              if detail.get("date_closed") else None),
                status=detail["status"],
                status_detail=detail.get("status_detail"),
                produto_total=produto_total,
                frete_comprador=frete_comprador,
                frete_vendedor=frete_vendedor,
                tarifa_bruta=tarifa_bruta,
                tarifa_refund=Decimal("0"),  # TODO refinar quando endpoint billing disponível
                refund_amount_partial=refund_partial,
                modalidade_anuncio=modalidade,
                logistic_type=logistic_type,
                shipping_mode=shipping_mode,
                breakdown_bucket=bucket,
                raw_json=json.dumps(detail),
                synced_at=datetime.utcnow(),
            )
            session.add(row)
            # Itens
            for it in detail.get("order_items", []):
                session.add(MLOrderItemCache(
                    order_id=order_id,
                    item_id=it["item"]["id"],
                    title=it["item"].get("title", ""),
                    seller_sku=it["item"].get("seller_custom_field") or it["item"].get("seller_sku"),
                    quantity=it["quantity"],
                    unit_price=Decimal(str(it["unit_price"])),
                    category_id=it["item"].get("category_id"),
                ))
        else:
            existing.status = detail["status"]
            existing.refund_amount_partial = refund_partial
            existing.synced_at = datetime.utcnow()
            existing.raw_json = json.dumps(detail)
        session.commit()
```

- [ ] **Step 2: Rodar testes existentes pra garantir que nada quebrou**

Run: `cd backend && pytest financeiro_ml/tests/ -v`
Expected: todos os 21+ testes PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/sync.py
git commit -m "feat(financeiro-ml): ensure_period_synced orchestrator with parallel sync"
```

---

## Task 13: Router REST — schemas Pydantic

**Files:**
- Create: `backend/financeiro_ml/router.py` (apenas schemas + estrutura inicial)

- [ ] **Step 1: Criar router com schemas Pydantic e rota /health**

Criar `backend/financeiro_ml/router.py`:

```python
"""Rotas REST do Resumo Financeiro Mercado Livre.
Permissão: somente Master.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ============ Schemas ============

class FilterParams(BaseModel):
    data_inicio: date
    data_fim: date
    sku: str | None = None
    mlb: str | None = None
    status: Literal["aprovado", "cancelado", "todos"] = "todos"
    modalidade: Literal["premium", "classico", "gratis", "todos"] = "todos"
    tipo_frete: Literal["me1", "me2", "sem_me", "full", "flex", "outro", "todos"] = "todos"
    custo_imposto: Literal["sem_custo", "sem_imposto", "sem_custo_imposto", "todos"] = "todos"
    considerar_frete_comprador: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class SkuPayload(BaseModel):
    custo_unit: Decimal
    imposto_pct: Decimal


# ============ Rotas ============

@router.get("/health")
async def health():
    """Verifica que o módulo está vivo e que ml_tokens tem token."""
    from database import SessionLocal
    from models import MLTokens
    with SessionLocal() as session:
        token = session.query(MLTokens).first()
        return {
            "ok": True,
            "ml_configured": token is not None,
            "user_id": token.user_id if token else None,
        }
```

- [ ] **Step 2: Plug no `main.py`**

Editar `backend/main.py`. Adicionar no bloco de imports (junto dos outros routers):

```python
from financeiro_ml import router as financeiro_ml
```

E no bloco de `app.include_router(...)`:

```python
app.include_router(financeiro_ml.router, prefix="/api/financeiro-ml", tags=["financeiro-ml"])
```

- [ ] **Step 3: Testar manualmente o health**

Run: `cd backend && uvicorn main:app --port 8001 &` (em outro terminal)
Run: `curl http://localhost:8001/api/financeiro-ml/health`
Expected: JSON `{"ok": true, "ml_configured": false/true, "user_id": ...}`

Parar o uvicorn antes de seguir.

- [ ] **Step 4: Commit**

```bash
git add backend/financeiro_ml/router.py backend/main.py
git commit -m "feat(financeiro-ml): router skeleton with health endpoint"
```

---

## Task 14: Router — cadastro SKU (CRUD + import)

**Files:**
- Modify: `backend/financeiro_ml/router.py`
- Create: `backend/financeiro_ml/tests/test_routers.py`

- [ ] **Step 1: Escrever testes do CRUD via TestClient**

Criar `backend/financeiro_ml/tests/test_routers.py`:

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
from models import SkuFinanceiro, Operator


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        if not s.query(Operator).filter_by(id=1).first():
            s.add(Operator(id=1, name="Test", badge="T", pin_code="1234"))
            s.commit()
        s.query(SkuFinanceiro).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app)


def test_put_sku_creates(client):
    r = client.put("/api/financeiro-ml/skus/SKU_TEST",
                    json={"custo_unit": "10.50", "imposto_pct": "8.00"})
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.query(SkuFinanceiro).filter_by(sku="SKU_TEST").first() is not None


def test_get_skus_lists(client):
    client.put("/api/financeiro-ml/skus/A", json={"custo_unit": "1", "imposto_pct": "9"})
    client.put("/api/financeiro-ml/skus/B", json={"custo_unit": "2", "imposto_pct": "9"})
    r = client.get("/api/financeiro-ml/skus")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2


def test_delete_sku(client):
    client.put("/api/financeiro-ml/skus/X", json={"custo_unit": "1", "imposto_pct": "9"})
    r = client.delete("/api/financeiro-ml/skus/X")
    assert r.status_code == 200
    r2 = client.delete("/api/financeiro-ml/skus/X")
    assert r2.status_code == 404
```

- [ ] **Step 2: Rodar — deve falhar (rotas não existem)**

Run: `cd backend && pytest financeiro_ml/tests/test_routers.py -v`
Expected: 404 ou erro.

- [ ] **Step 3: Adicionar rotas SKU em `financeiro_ml/router.py`**

Adicionar ao final do arquivo:

```python
from fastapi import UploadFile, File
from financeiro_ml.sku_service import upsert_sku, list_skus, delete_sku, import_excel

# TODO: substituir por dependência real de auth Master quando integrar com auth do projeto
def require_master() -> int:
    """Stub. Retorna operator_id 1. Trocar pela dependência real depois."""
    return 1


@router.get("/skus")
async def get_skus(q: str | None = None, operator_id: int = Depends(require_master)):
    items = list_skus(q)
    return {
        "items": [
            {"sku": k, "custo_unit": str(v["custo_unit"]), "imposto_pct": str(v["imposto_pct"]),
             "updated_at": v["updated_at"].isoformat() if v.get("updated_at") else None}
            for k, v in items.items()
        ],
        "total": len(items),
    }


@router.put("/skus/{sku}")
async def put_sku(sku: str, payload: SkuPayload, operator_id: int = Depends(require_master)):
    upsert_sku(sku, custo_unit=payload.custo_unit, imposto_pct=payload.imposto_pct,
                updated_by_id=operator_id)
    return {"ok": True}


@router.delete("/skus/{sku}")
async def del_sku(sku: str, operator_id: int = Depends(require_master)):
    if not delete_sku(sku):
        raise HTTPException(status_code=404, detail="SKU não encontrado")
    return {"ok": True}


@router.post("/skus/import-excel")
async def import_skus_excel(file: UploadFile = File(...), operator_id: int = Depends(require_master)):
    content = await file.read()
    import io
    result = import_excel(io.BytesIO(content), updated_by_id=operator_id)
    return result
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_routers.py -v`
Expected: 3 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/router.py backend/financeiro_ml/tests/test_routers.py
git commit -m "feat(financeiro-ml): SKU CRUD endpoints + excel import"
```

---

## Task 15: Router — endpoint /resumo

**Files:**
- Modify: `backend/financeiro_ml/router.py`
- Modify: `backend/financeiro_ml/tests/test_routers.py`

- [ ] **Step 1: Escrever teste do endpoint (com sync mockado)**

Adicionar ao `financeiro_ml/tests/test_routers.py`:

```python
from unittest.mock import patch, AsyncMock
from datetime import date


def test_resumo_returns_cards(client):
    async def fake_sync(*a, **k):
        return {"dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0}
    with patch("financeiro_ml.router.ensure_period_synced", new=AsyncMock(side_effect=fake_sync)):
        r = client.post("/api/financeiro-ml/resumo", json={
            "data_inicio": str(date.today()),
            "data_fim": str(date.today()),
        })
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "pizza" in body
    assert "tabela" in body
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd backend && pytest financeiro_ml/tests/test_routers.py::test_resumo_returns_cards -v`
Expected: 404 ou erro.

- [ ] **Step 3: Adicionar endpoint /resumo em `financeiro_ml/router.py`**

Adicionar:

```python
from datetime import datetime, time
from financeiro_ml.sync import ensure_period_synced
from financeiro_ml.aggregator import aggregate
from models import MLOrderCache, MLOrderItemCache, SkuFinanceiro
from sqlalchemy import and_


@router.post("/resumo")
async def get_resumo(params: FilterParams, operator_id: int = Depends(require_master)):
    sync_report = await ensure_period_synced(params.data_inicio, params.data_fim)

    from database import SessionLocal
    with SessionLocal() as session:
        date_from = datetime.combine(params.data_inicio, time.min)
        date_to = datetime.combine(params.data_fim, time.max)

        q = session.query(MLOrderCache).filter(
            and_(MLOrderCache.date_created >= date_from, MLOrderCache.date_created <= date_to)
        )
        if params.status == "aprovado":
            q = q.filter(MLOrderCache.status == "paid")
        elif params.status == "cancelado":
            q = q.filter(MLOrderCache.status == "cancelled")

        orders = [_row_to_dict_order(r) for r in q.all()]
        order_ids = [o["order_id"] for o in orders]

        items_q = session.query(MLOrderItemCache).filter(MLOrderItemCache.order_id.in_(order_ids))
        if params.sku:
            items_q = items_q.filter(MLOrderItemCache.seller_sku == params.sku)
        items = [_row_to_dict_item(r) for r in items_q.all()]

        skus_rows = session.query(SkuFinanceiro).all()
        sku_financeiro = {
            r.sku: {"custo_unit": Decimal(str(r.custo_unit)), "imposto_pct": Decimal(str(r.imposto_pct))}
            for r in skus_rows
        }

    result = aggregate(orders, items, sku_financeiro)

    # Paginação da tabela
    total = len(result["tabela"])
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    result["tabela"] = result["tabela"][start:end]
    result["pagination"] = {
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": (total + params.page_size - 1) // params.page_size,
    }
    result["sync_report"] = sync_report
    return result


def _row_to_dict_order(r) -> dict:
    return {
        "order_id": r.order_id,
        "status": r.status,
        "date_created": r.date_created,
        "produto_total": Decimal(str(r.produto_total)),
        "frete_comprador": Decimal(str(r.frete_comprador)),
        "frete_vendedor": Decimal(str(r.frete_vendedor)),
        "tarifa_bruta": Decimal(str(r.tarifa_bruta)),
        "tarifa_refund": Decimal(str(r.tarifa_refund)),
        "refund_amount_partial": Decimal(str(r.refund_amount_partial)),
        "logistic_type": r.logistic_type,
        "shipping_mode": r.shipping_mode,
        "modalidade_anuncio": r.modalidade_anuncio,
        "breakdown_bucket": r.breakdown_bucket,
    }


def _row_to_dict_item(r) -> dict:
    return {
        "order_id": r.order_id,
        "item_id": r.item_id,
        "title": r.title,
        "seller_sku": r.seller_sku,
        "quantity": r.quantity,
        "unit_price": Decimal(str(r.unit_price)),
    }
```

Antes de aplicar: garantir que no `JSONResponse` o `Decimal` serializa. FastAPI já trata via Pydantic v2, mas como retornamos dict cru, precisamos converter Decimal pra str/float. Acrescentar conversão antes do return:

```python
    return _json_safe(result)


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd backend && pytest financeiro_ml/tests/test_routers.py -v`
Expected: 4 testes PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/router.py backend/financeiro_ml/tests/test_routers.py
git commit -m "feat(financeiro-ml): /resumo endpoint with aggregation and pagination"
```

---

## Task 16: Router — export Excel/CSV

**Files:**
- Modify: `backend/financeiro_ml/router.py`

- [ ] **Step 1: Implementar `/export`**

Adicionar:

```python
from fastapi.responses import StreamingResponse
import io
import csv
from openpyxl import Workbook


@router.post("/export")
async def export_resumo(params: FilterParams, formato: Literal["excel", "csv"] = "excel",
                          operator_id: int = Depends(require_master)):
    """Exporta a tabela do resumo (sem paginação) no formato pedido."""
    full = await get_resumo(FilterParams(**{**params.dict(), "page": 1, "page_size": 100000}),
                             operator_id=operator_id)
    rows = full["tabela"]

    if formato == "csv":
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")),
                                 media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=resumo.csv"})

    # Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    if rows:
        ws.append(list(rows[0].keys()))
        for r in rows:
            ws.append([r.get(k) for k in rows[0].keys()])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return StreamingResponse(bio,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=resumo.xlsx"})
```

- [ ] **Step 2: Rodar testes pra garantir nada quebrou**

Run: `cd backend && pytest financeiro_ml/tests/ -v`
Expected: todos PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/router.py
git commit -m "feat(financeiro-ml): export endpoint (excel/csv)"
```

---

# Frontend

## Task 17: Instalar libs frontend

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Instalar via npm**

Run: `cd frontend && npm install recharts@^2.13.0 @tanstack/react-query@^5.59.0 @tanstack/react-table@^8.20.0 @radix-ui/react-tooltip@^1.1.2`
Expected: 4 libs adicionadas, `package-lock.json` atualizado.

- [ ] **Step 2: Conferir build local**

Run: `cd frontend && npm run build`
Expected: build sucesso (zero erros).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(financeiro-ml): add recharts, tanstack query/table, radix tooltip"
```

---

## Task 18: Setup QueryClient + provider

**Files:**
- Create: `frontend/src/lib/queryClient.js`
- Modify: `frontend/src/main.jsx`

- [ ] **Step 1: Criar `queryClient.js`**

Criar `frontend/src/lib/queryClient.js`:

```javascript
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,            // 30s — dado fresco por 30s
      gcTime: 5 * 60_000,           // 5min — mantém em memória
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})
```

- [ ] **Step 2: Envolver app em `QueryClientProvider`**

Editar `frontend/src/main.jsx`. Adicionar import:

```javascript
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
```

Envolver o `<App />` no provider — exemplo (ajustar à estrutura existente):

```jsx
<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

- [ ] **Step 3: Validar build**

Run: `cd frontend && npm run build`
Expected: sucesso.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/queryClient.js frontend/src/main.jsx
git commit -m "feat(financeiro-ml): setup TanStack QueryClient at root"
```

---

## Task 19: API client frontend

**Files:**
- Create: `frontend/src/financeiro-ml/api.js`

- [ ] **Step 1: Criar wrappers**

Criar `frontend/src/financeiro-ml/api.js`:

```javascript
const BASE = '/api/financeiro-ml'

async function jsonOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText} ${text}`)
  }
  return res.json()
}

export const financeiroMLApi = {
  health: () => fetch(`${BASE}/health`).then(jsonOrThrow),

  getResumo: (filters) =>
    fetch(`${BASE}/resumo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    }).then(jsonOrThrow),

  listSkus: (q = '') =>
    fetch(`${BASE}/skus?q=${encodeURIComponent(q)}`).then(jsonOrThrow),

  putSku: (sku, { custo_unit, imposto_pct }) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ custo_unit, imposto_pct }),
    }).then(jsonOrThrow),

  deleteSku: (sku) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, { method: 'DELETE' }).then(jsonOrThrow),

  importSkusExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${BASE}/skus/import-excel`, { method: 'POST', body: fd })
    return jsonOrThrow(res)
  },

  exportResumo: (filters, formato = 'excel') =>
    fetch(`${BASE}/export?formato=${formato}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    }).then((res) => res.blob()),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/api.js
git commit -m "feat(financeiro-ml): frontend api client wrappers"
```

---

## Task 20: Component Tooltip (wrapper Radix)

**Files:**
- Create: `frontend/src/financeiro-ml/components/Tooltip.jsx`

- [ ] **Step 1: Criar wrapper**

Criar `frontend/src/financeiro-ml/components/Tooltip.jsx`:

```jsx
import * as RT from '@radix-ui/react-tooltip'

export function Tooltip({ content, children }) {
  if (!content) return children
  return (
    <RT.Provider delayDuration={200}>
      <RT.Root>
        <RT.Trigger asChild>{children}</RT.Trigger>
        <RT.Portal>
          <RT.Content className="rounded bg-slate-900 text-white text-xs px-2 py-1 max-w-xs shadow-lg z-50" sideOffset={4}>
            {content}
            <RT.Arrow className="fill-slate-900" />
          </RT.Content>
        </RT.Portal>
      </RT.Root>
    </RT.Provider>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/components/Tooltip.jsx
git commit -m "feat(financeiro-ml): Tooltip wrapper using Radix"
```

---

## Task 21: Component KPICards

**Files:**
- Create: `frontend/src/financeiro-ml/components/KPICards.jsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/financeiro-ml/components/KPICards.jsx`:

```jsx
import { Tooltip } from './Tooltip'

const fmt = (n) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(n ?? 0)
const fmtPct = (n) => `${(n ?? 0).toFixed(2).replace('.', ',')}%`
const fmtInt = (n) => new Intl.NumberFormat('pt-BR').format(n ?? 0)

function Card({ label, value, sub, tooltip, color = 'gray' }) {
  const bg = {
    green: 'bg-emerald-50 border-emerald-200',
    red: 'bg-red-50 border-red-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    blue: 'bg-blue-50 border-blue-200',
    gray: 'bg-gray-50 border-gray-200',
  }[color]

  return (
    <Tooltip content={tooltip}>
      <div className={`border rounded-lg p-3 ${bg}`}>
        <div className="text-xs text-gray-600">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
        {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
      </div>
    </Tooltip>
  )
}

export function KPICards({ cards }) {
  if (!cards) return null
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
      <Card label="Vendas Aprovadas" value={fmt(cards.vendas_aprovadas)}
            sub={`Faturamento ML ${fmt(cards.faturamento_ml)} · Canceladas ${fmt(cards.vendas_canceladas)}`}
            tooltip="Considera valor do produto + frete pago pelo comprador." />
      <Card label="Custo & Imposto" value={fmt(cards.custo_imposto_total)} color="red"
            sub={`Custo ${fmt(cards.custo_total)} · Imposto ${fmt(cards.imposto_total)}`}
            tooltip="Valores vinculados aos SKUs cadastrados em Cadastro SKU." />
      <Card label="Tarifa de Venda" value={fmt(cards.tarifa_venda)} color="yellow"
            tooltip="Tarifa ML descontada de eventual refund parcial." />
      <Card label="Frete Total" value={fmt(cards.frete_total)} color="blue"
            sub={`Comprador ${fmt(cards.frete_comprador_total)} · Vendedor ${fmt(cards.frete_vendedor_total)}`}
            tooltip="Soma dos fretes em vendas aprovadas." />
      <Card label="Margem de Contribuição" value={fmt(cards.mc_total)} color="green"
            sub={`(${fmtPct(cards.mc_pct_global)})`}
            tooltip="Vendas aprovadas menos custo, imposto, tarifa, frete vendedor e devolução parcial." />

      <Card label="Places/Coleta" value={fmt(cards.breakdown_logistico?.places_coleta || 0)} />
      <Card label="Flex" value={fmt(cards.breakdown_logistico?.flex || 0)} />
      <Card label="Full" value={fmt(cards.breakdown_logistico?.full || 0)} />
      <Card label="ME1" value={fmt(cards.breakdown_logistico?.me1 || 0)} />
      <Card label="Outros" value={fmt(cards.breakdown_logistico?.outros || 0)} />

      <Card label="Qtd Vendas Aprovadas" value={fmtInt(cards.qtd_vendas_aprovadas)}
            sub={`${fmtInt(cards.unidades_aprovadas)} unidades`} />
      <Card label="Qtd Total Vendas" value={`${fmtInt(cards.qtd_total_vendas)}`}
            sub={`canceladas: ${fmtInt(cards.qtd_vendas_canceladas)}`} />
      <Card label="Ticket Médio" value={fmt(cards.ticket_medio)} />
      <Card label="Ticket Médio MC" value={fmt(cards.ticket_mc)} sub={fmtPct(cards.mc_pct_global)} />
      <Card label="Devoluções Parciais" value={fmt(cards.devolucoes_parciais_valor)} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/components/KPICards.jsx
git commit -m "feat(financeiro-ml): KPICards component with 15 cards"
```

---

## Task 22: Component PizzaChart

**Files:**
- Create: `frontend/src/financeiro-ml/components/PizzaChart.jsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/financeiro-ml/components/PizzaChart.jsx`:

```jsx
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  Custo: '#f97316',
  Imposto: '#dc2626',
  Tarifa: '#eab308',
  Frete: '#3b82f6',
  MC: '#10b981',
}

export function PizzaChart({ pizza }) {
  if (!pizza || pizza.length === 0) {
    return <div className="text-gray-400 text-sm">Sem dados pra exibir.</div>
  }
  const data = pizza.map((s) => ({ name: s.label, value: parseFloat(s.valor), pct: s.pct }))

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="text-sm font-semibold mb-2">Representação Gráfica</h3>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}
               label={(d) => `${d.pct.toFixed(1)}%`}>
            {data.map((d) => (
              <Cell key={d.name} fill={COLORS[d.name] || '#888'} />
            ))}
          </Pie>
          <Tooltip formatter={(v) => `R$ ${v.toFixed(2)}`} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-500 mt-2">* O frete pago pelo comprador não é considerado no gráfico.</p>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/components/PizzaChart.jsx
git commit -m "feat(financeiro-ml): PizzaChart donut with 5 slices"
```

---

## Task 23: Component FiltrosBar

**Files:**
- Create: `frontend/src/financeiro-ml/components/FiltrosBar.jsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/financeiro-ml/components/FiltrosBar.jsx`:

```jsx
import { useState } from 'react'

const today = () => new Date().toISOString().slice(0, 10)

export function FiltrosBar({ onBuscar, loading }) {
  const [filtros, setFiltros] = useState({
    data_inicio: today(),
    data_fim: today(),
    sku: '',
    mlb: '',
    status: 'todos',
    modalidade: 'todos',
    tipo_frete: 'todos',
    custo_imposto: 'todos',
    considerar_frete_comprador: false,
    page: 1,
    page_size: 50,
  })

  const set = (key, value) => setFiltros((f) => ({ ...f, [key]: value, page: 1 }))

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="text-sm font-semibold mb-3">Filtrar Busca</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <label className="text-xs">
          Data Início
          <input type="date" value={filtros.data_inicio} onChange={(e) => set('data_inicio', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Data Fim
          <input type="date" value={filtros.data_fim} onChange={(e) => set('data_fim', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          SKU
          <input value={filtros.sku} onChange={(e) => set('sku', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Nº Pedido / MLB
          <input value={filtros.mlb} onChange={(e) => set('mlb', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Status Venda
          <select value={filtros.status} onChange={(e) => set('status', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="aprovado">Aprovados</option>
            <option value="cancelado">Cancelados</option>
          </select>
        </label>
        <label className="text-xs">
          Modalidade (Anúncio)
          <select value={filtros.modalidade} onChange={(e) => set('modalidade', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="premium">Premium</option>
            <option value="classico">Clássico</option>
            <option value="gratis">Grátis</option>
          </select>
        </label>
        <label className="text-xs">
          Tipo do Frete
          <select value={filtros.tipo_frete} onChange={(e) => set('tipo_frete', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="me1">Mercado Envios 1</option>
            <option value="me2">Mercado Envios 2</option>
            <option value="sem_me">S/ Mercado Envios</option>
            <option value="full">FULL</option>
            <option value="flex">Flex</option>
            <option value="outro">Outro (a Combinar)</option>
          </select>
        </label>
        <label className="text-xs">
          Custo & Imposto
          <select value={filtros.custo_imposto} onChange={(e) => set('custo_imposto', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="sem_custo">Somente sem Custo</option>
            <option value="sem_imposto">Somente sem Imposto</option>
            <option value="sem_custo_imposto">Somente sem Custo e Imposto</option>
          </select>
        </label>
        <label className="text-xs flex items-center gap-2 mt-4">
          <input type="checkbox" checked={filtros.considerar_frete_comprador}
                 onChange={(e) => set('considerar_frete_comprador', e.target.checked)} />
          Considerar frete comprador
        </label>
      </div>
      <button onClick={() => onBuscar(filtros)} disabled={loading}
              className="mt-3 px-4 py-2 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50">
        {loading ? 'Buscando…' : 'Buscar'}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/components/FiltrosBar.jsx
git commit -m "feat(financeiro-ml): FiltrosBar component"
```

---

## Task 24: Component TabelaVendas

**Files:**
- Create: `frontend/src/financeiro-ml/components/TabelaVendas.jsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/financeiro-ml/components/TabelaVendas.jsx`:

```jsx
import { useReactTable, getCoreRowModel, getSortedRowModel, flexRender } from '@tanstack/react-table'
import { useState } from 'react'

const fmt = (n) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n ?? 0)

const columns = [
  { accessorKey: 'anuncio', header: 'Anúncio' },
  { accessorKey: 'sku', header: 'SKU' },
  { accessorKey: 'data', header: 'Data', cell: (i) => i.getValue()?.slice(0, 10) },
  { accessorKey: 'frete_label', header: 'Frete' },
  { accessorKey: 'valor_unit', header: 'Valor Unit.', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'qty', header: 'Qtd.' },
  { accessorKey: 'faturamento_ml', header: 'Faturamento ML', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'custo', header: 'Custo (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'imposto', header: 'Imposto (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'tarifa', header: 'Tarifa (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'frete_comprador', header: 'Frete Comp. (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'frete_vendedor', header: 'Frete Vend. (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'mc', header: 'MC (=)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'mc_pct', header: 'MC %', cell: (i) => `${fmt(i.getValue())}%` },
]

export function TabelaVendas({ data, pagination, onPageChange, onPageSizeChange }) {
  const [sorting, setSorting] = useState([])
  const table = useReactTable({
    data: data || [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="border rounded-lg bg-white overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th key={h.id} className="px-3 py-2 text-left font-semibold cursor-pointer"
                    onClick={h.column.getToggleSortingHandler()}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                  {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted()] ?? ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-t hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell ?? cell.column.columnDef.accessorKey, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {pagination && (
        <div className="flex items-center justify-between p-2 border-t bg-gray-50 text-xs">
          <span>
            {(pagination.page - 1) * pagination.page_size + 1}–
            {Math.min(pagination.page * pagination.page_size, pagination.total)} de {pagination.total}
          </span>
          <div className="flex gap-2 items-center">
            <button disabled={pagination.page <= 1} onClick={() => onPageChange(pagination.page - 1)}
                    className="px-2 py-1 border rounded disabled:opacity-50">‹</button>
            <span>{pagination.page} / {pagination.total_pages}</span>
            <button disabled={pagination.page >= pagination.total_pages}
                    onClick={() => onPageChange(pagination.page + 1)}
                    className="px-2 py-1 border rounded disabled:opacity-50">›</button>
            <select value={pagination.page_size} onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
                    className="border rounded px-1 py-0.5 ml-2">
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/financeiro-ml/components/TabelaVendas.jsx
git commit -m "feat(financeiro-ml): TabelaVendas with TanStack Table"
```

---

## Task 25: Página Resumo

**Files:**
- Create: `frontend/src/financeiro-ml/pages/Resumo.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Criar página**

Criar `frontend/src/financeiro-ml/pages/Resumo.jsx`:

```jsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { financeiroMLApi } from '../api'
import { FiltrosBar } from '../components/FiltrosBar'
import { KPICards } from '../components/KPICards'
import { PizzaChart } from '../components/PizzaChart'
import { TabelaVendas } from '../components/TabelaVendas'

export default function Resumo() {
  const [resultado, setResultado] = useState(null)
  const [filtrosAtuais, setFiltrosAtuais] = useState(null)

  const mutation = useMutation({
    mutationFn: (filtros) => financeiroMLApi.getResumo(filtros),
    onSuccess: (data, filtros) => {
      setResultado(data)
      setFiltrosAtuais(filtros)
    },
  })

  const onPage = (page) => mutation.mutate({ ...filtrosAtuais, page })
  const onPageSize = (page_size) => mutation.mutate({ ...filtrosAtuais, page: 1, page_size })

  const exportar = async (formato) => {
    if (!filtrosAtuais) return
    const blob = await financeiroMLApi.exportResumo(filtrosAtuais, formato)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `resumo.${formato === 'csv' ? 'csv' : 'xlsx'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Resumo Financeiro Mercado Livre</h1>
      <FiltrosBar onBuscar={mutation.mutate} loading={mutation.isPending} />
      {mutation.isError && (
        <div className="border border-red-300 bg-red-50 p-3 rounded text-red-700 text-sm">
          Erro: {String(mutation.error)}
        </div>
      )}
      {resultado && (
        <>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2"><KPICards cards={resultado.cards} /></div>
            <PizzaChart pizza={resultado.pizza} />
          </div>
          <div className="flex gap-2">
            <button onClick={() => exportar('excel')} className="px-3 py-1.5 text-sm border rounded">Exportar Excel</button>
            <button onClick={() => exportar('csv')} className="px-3 py-1.5 text-sm border rounded">Exportar CSV</button>
          </div>
          <TabelaVendas
            data={resultado.tabela}
            pagination={resultado.pagination}
            onPageChange={onPage}
            onPageSizeChange={onPageSize}
          />
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Adicionar rota em `App.jsx`**

Em `frontend/src/App.jsx`, adicionar import e rota (ajustar à estrutura existente do roteamento):

```jsx
import Resumo from './financeiro-ml/pages/Resumo'

// dentro do <Routes>:
<Route path="/financeiro-ml/resumo" element={<Resumo />} />
```

- [ ] **Step 3: Validar build**

Run: `cd frontend && npm run build`
Expected: sucesso.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/financeiro-ml/pages/Resumo.jsx frontend/src/App.jsx
git commit -m "feat(financeiro-ml): main Resumo page"
```

---

## Task 26: Página cadastro SKU

**Files:**
- Create: `frontend/src/financeiro-ml/pages/Skus.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Criar página**

Criar `frontend/src/financeiro-ml/pages/Skus.jsx`:

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { financeiroMLApi } from '../api'

export default function Skus() {
  const [q, setQ] = useState('')
  const [novoSku, setNovoSku] = useState('')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['skus', q],
    queryFn: () => financeiroMLApi.listSkus(q),
  })

  const salvar = useMutation({
    mutationFn: ({ sku, custo_unit, imposto_pct }) =>
      financeiroMLApi.putSku(sku, { custo_unit: String(custo_unit), imposto_pct: String(imposto_pct) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  const remover = useMutation({
    mutationFn: (sku) => financeiroMLApi.deleteSku(sku),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  const importar = useMutation({
    mutationFn: (file) => financeiroMLApi.importSkusExcel(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Cadastro SKU — Custo & Imposto</h1>

      <div className="flex gap-2 items-center">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar SKU…"
               className="border rounded px-2 py-1 flex-1" />
        <label className="px-3 py-1.5 border rounded cursor-pointer">
          Importar Excel
          <input type="file" accept=".xlsx" hidden
                 onChange={(e) => e.target.files[0] && importar.mutate(e.target.files[0])} />
        </label>
      </div>

      {importar.data && (
        <div className="text-xs bg-green-50 border border-green-200 p-2 rounded">
          Import: {importar.data.created} criados · {importar.data.updated} atualizados ·
          {importar.data.errors?.length || 0} erros
        </div>
      )}

      <div className="flex gap-2">
        <input value={novoSku} onChange={(e) => setNovoSku(e.target.value)} placeholder="Novo SKU"
               className="border rounded px-2 py-1" />
        <button onClick={() => {
          if (novoSku.trim()) {
            salvar.mutate({ sku: novoSku.trim(), custo_unit: '0', imposto_pct: '0' })
            setNovoSku('')
          }
        }} className="px-3 py-1.5 bg-violet-600 text-white rounded">
          Adicionar
        </button>
      </div>

      <table className="min-w-full border rounded bg-white text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left">SKU</th>
            <th className="px-3 py-2 text-left">Custo Unit. (R$)</th>
            <th className="px-3 py-2 text-left">Imposto (%)</th>
            <th className="px-3 py-2 text-left">Ações</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan="4" className="p-3 text-center">Carregando…</td></tr>}
          {data?.items?.map((row) => (
            <SkuRow key={row.sku} row={row}
                    onSave={(updates) => salvar.mutate({ sku: row.sku, ...updates })}
                    onDelete={() => remover.mutate(row.sku)} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SkuRow({ row, onSave, onDelete }) {
  const [custo, setCusto] = useState(row.custo_unit)
  const [imposto, setImposto] = useState(row.imposto_pct)
  const dirty = custo !== row.custo_unit || imposto !== row.imposto_pct
  return (
    <tr className="border-t">
      <td className="px-3 py-2 font-mono">{row.sku}</td>
      <td className="px-3 py-2">
        <input value={custo} onChange={(e) => setCusto(e.target.value)} className="w-24 border rounded px-1" />
      </td>
      <td className="px-3 py-2">
        <input value={imposto} onChange={(e) => setImposto(e.target.value)} className="w-20 border rounded px-1" />
      </td>
      <td className="px-3 py-2 flex gap-2">
        <button disabled={!dirty} onClick={() => onSave({ custo_unit: custo, imposto_pct: imposto })}
                className="px-2 py-1 text-xs border rounded disabled:opacity-30">Salvar</button>
        <button onClick={onDelete} className="px-2 py-1 text-xs border rounded text-red-600">Excluir</button>
      </td>
    </tr>
  )
}
```

- [ ] **Step 2: Adicionar rota**

Em `frontend/src/App.jsx`:

```jsx
import Skus from './financeiro-ml/pages/Skus'

// dentro do <Routes>:
<Route path="/financeiro-ml/skus" element={<Skus />} />
```

- [ ] **Step 3: Validar build**

Run: `cd frontend && npm run build`
Expected: sucesso.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/financeiro-ml/pages/Skus.jsx frontend/src/App.jsx
git commit -m "feat(financeiro-ml): SKU registration page"
```

---

## Task 27: Adicionar entrada no menu lateral

**Files:**
- Modify: arquivo do menu/layout (a localizar — provavelmente `frontend/src/components/Layout.jsx` ou similar)

- [ ] **Step 1: Localizar componente do menu**

Run: `cd frontend && grep -rn "financeiro\|Boletos\|Master" src/components/ src/pages/ 2>/dev/null | grep -i "menu\|sidebar\|nav" | head -5`

Identificar o arquivo que define o menu lateral (provavelmente um `<aside>` ou `<nav>`).

- [ ] **Step 2: Adicionar 2 entradas**

No arquivo identificado, adicionar (estilizado conforme padrão existente):

```jsx
{isMaster && (
  <>
    <NavLink to="/financeiro-ml/resumo">Resumo Financeiro ML</NavLink>
    <NavLink to="/financeiro-ml/skus">Cadastro Custo SKU</NavLink>
  </>
)}
```

Se o flag `isMaster` não existir, replicar a lógica usada por `/financeiro` (Boletos) que já é restrito a Master.

- [ ] **Step 3: Validar visual no navegador**

Run: `cd frontend && npm run dev` (em paralelo: `cd backend && uvicorn main:app --port 8001`)
Abrir `http://localhost:5173`, logar como Master, conferir que aparecem as 2 entradas e clicam pras páginas certas.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/<arquivo-menu>.jsx
git commit -m "feat(financeiro-ml): add sidebar entries (Master-only)"
```

---

## Task 28: Smoke test manual + ajuste de mapeamentos ML

**Files:**
- Modify (conforme descobertas): `backend/financeiro_ml/aggregator.py` (mapeamento `_logistic_bucket`), `backend/financeiro_ml/sync.py` (campos exatos), `Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md` (atualizar com descobertas)

> Essa task fecha os 4 pontos 🟡 do estudo (§13 da spec). Só executar após Tasks 1-27 concluídas.

- [ ] **Step 1: Configurar .env real local**

Editar `.env` (não `.env.example`!) com as credenciais ML reais — copiar de `Devoluçao/.env` se existir.

```
ML_CLIENT_ID=<real>
ML_CLIENT_SECRET=<real>
ML_USER_ID=221832146
ML_ACCESS_TOKEN=<real>
ML_REFRESH_TOKEN=<real>
```

- [ ] **Step 2: Reiniciar backend pra seed de ml_tokens**

Run: `cd backend && uvicorn main:app --port 8001 --reload`
Expected: log `[financeiro-ml] ml_tokens seeded from env` na primeira execução.

- [ ] **Step 3: Validar health**

Run: `curl http://localhost:8001/api/financeiro-ml/health`
Expected: `{"ok": true, "ml_configured": true, "user_id": 221832146}`.

- [ ] **Step 4: Disparar busca de 1 dia (hoje)**

No browser, acessar `http://localhost:5173/financeiro-ml/resumo`, preencher data_inicio=data_fim=hoje, clicar Buscar.

Expected:
- Backend faz fetch ML real.
- Cards aparecem (mesmo com MC = 0 inicialmente porque SKU sem cadastro).
- Tabela populada.

Se erro: ler logs do backend, conferir headers/payload, ajustar.

- [ ] **Step 5: Comparar 1 pedido contra Mercado Turbo**

Abrir o MT no browser, filtrar 1 dia, escolher 1 pedido. Comparar os valores linha-a-linha contra o NVS:
- Valor Unit
- Qtd
- Faturamento ML
- Frete Comprador
- Frete Vendedor
- Tarifa

Identificar divergências.

- [ ] **Step 6: Refinar campos ML baseado em divergências**

Onde `frete_vendedor` divergir: inspecionar `raw_json` da row no SQLite, identificar o campo correto (`shipping.list_cost` vs outro). Ajustar `_sync_single_day._save_order`.

Onde `tarifa` divergir: provavelmente endpoint de billing faltando. Anotar e adiar.

Atualizar `Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md` §12 com cada descoberta.

- [ ] **Step 7: Validar mapeamento de modalidade de frete**

Filtrar por cada uma das 6 modalidades no UI. Conferir que volta o conjunto certo de pedidos. Onde errar: ajustar `_logistic_bucket` em `ml_aggregator.py`.

- [ ] **Step 8: Cadastrar 1 SKU teste**

Em `/financeiro-ml/skus`, cadastrar custo + imposto pro SKU 577 (do exemplo). Voltar ao /resumo, refazer Buscar. Conferir que MC agora aparece corretamente naquela linha.

- [ ] **Step 9: Validar checkbox "Considerar frete comprador"**

Marcar/desmarcar o checkbox, refazer Buscar, observar mudança no card de MC. Documentar comportamento esperado na spec.

- [ ] **Step 10: Commit dos ajustes finais**

```bash
git add backend/financeiro_ml/sync.py backend/financeiro_ml/aggregator.py "Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md"
git commit -m "fix(financeiro-ml): refine ML field mappings after live smoke test"
```

- [ ] **Step 11: Documentar resultado em CODEBASE.md**

Adicionar seção curta em `CODEBASE.md` mencionando o novo módulo `/api/financeiro-ml/*` e as 5 tabelas novas.

```bash
git add CODEBASE.md
git commit -m "docs(financeiro-ml): update CODEBASE map"
```

---

# Conclusão

Após Tasks 1-28: módulo funcionando localmente, smoke test validado contra MT real, doc atualizado. **Não fazer deploy** (`publicar_producao.bat`) sem aprovação do Julio.

Próximo passo após merge: cancelar/degradar assinatura MT.

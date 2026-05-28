# INCIDENTE PRODUÇÃO — Painel Mercado Turbo (NVS-WMS)
**Data:** 2026-05-27 (noite, ~21:00 BRT em diante)
**Status no momento de escrever este doc:** Não resolvido. Em prod, /api/financeiro-ml/resumo retorna `dias_falhos: N`, sem trazer dados.
**Para quem ler isto:** Você é um especialista chamado para o caso. Leia tudo. Há contexto crítico embutido nas seções "Tentativa N".

---

## 1. Contexto do projeto

- **Stack:** FastAPI + SQLAlchemy + SQLite (backend) / React + Vite (frontend) / hospedagem Railway.
- **Repo:** `/Users/julio/Documents/Antigra/warehouse-picker v2` (branch padrão: `main`; deploy via script `publicar_producao.command` → push para `origin/main` → Railway auto-deploy).
- **URL prod:** `https://nvs-wms-v2-production.up.railway.app`
- **Railway project ID:** `d377de82-4ee6-42b7-8196-8f5f99915f4b`
- **Service:** `nvs-wms-v2` (1 replica, EU-West, volume `nvs-wms-v2-volume` montado para SQLite).
- **Módulo crítico:** `backend/financeiro_ml/` (cliente ML async, sync orquestrador, agregador, router FastAPI). Tabelas próprias: `ml_tokens`, `ml_day_sync_status`, `ml_order_cache`, `ml_order_item_cache`, `sku_financeiro`.
- **Conta ML:** seller `NOVAESMOTOPEÇAS`, user_id `221832146`, ~284k pedidos históricos no ML.

## 2. O que foi feito antes do incidente (deploys deste dia)

Hoje (27/05/2026) foi o **primeiro deploy em produção** do módulo Mercado Turbo (financeiro_ml). Em desenvolvimento o módulo já estava testado e funcionando há semanas. Sequência de deploys de hoje:

1. **Deploy inicial do módulo financeiro_ml** (commit `ee4ca75` ou anterior — antes do incidente). Subiu todo o código: client.py, sync.py, aggregator.py, router.py, frontend (Resumo, Cadastro SKU, etc.). Painel acessível em `/financeiro-ml/resumo`.
2. **Variáveis ML configuradas no Railway:**
   - `ML_CLIENT_ID = 8806146527865119`
   - `ML_CLIENT_SECRET = 6qLAQ7NcFqbQjOYRrtfW1Q3bRKjVMOII`
   - `ML_USER_ID = 221832146`
   - `ML_ACCESS_TOKEN`, `ML_REFRESH_TOKEN` — valores INICIAIS do seed `.env` (que mais tarde foram identificados como obsoletos)
   - `ML_REDIRECT_URI` (vazio no `.env`; no painel ML developer está `https://www.youtube.com`)
   - `ML_SYNC_MAX_DAYS_PARALLEL = 5`
   - `ML_SYNC_MAX_ORDERS_PARALLEL = 10`
3. **Ao clicar "Buscar" no painel pela primeira vez**, retornou `cards={vendas_aprovadas:0,…}`, `sync_report.dias_falhos = 8` (todos os 8 dias do range falharam, 0 sucesso, 0 orders sincronizados). UI exibe "Sem dados pra exibir".

## 3. Linha do tempo das tentativas de fix (ordem cronológica)

### Tentativa 1 — Adicionar logging
**Problema:** O `except Exception` em `_sync_single_day` apenas salvava `str(e)` em `MLDaySyncStatus.error_message`. Não havia log no stdout, então Railway logs não mostravam o erro raiz.

**Fix aplicado** (commit `0e70690`):
- `sync.py` linha 177: adicionou `trace.exception(f"sync.day[{d}] FAILED ...")` + `traceback.format_exc()` salvo em `error_message[:4000]`.
- `router.py`: adicionou endpoint `GET /api/financeiro-ml/_debug/sync-status` que retorna últimos 30 dias da tabela `ml_day_sync_status` (status, error_message, last_synced_at).

**Resultado:** O endpoint /_debug/sync-status revelou que erro raiz era `Client error '429 Too Many Requests' for url '.../orders/search?seller=221832146&...'`. Confirmou rate limit do Mercado Livre.

### Tentativa 2 — Reduzir paralelismo do sync (env vars)
**Hipótese:** 5 dias paralelos × 10 orders paralelos = 50 requests simultâneos. ML cortou com 429.

**Fix aplicado:** Pediu pro usuário trocar no Railway:
- `ML_SYNC_MAX_DAYS_PARALLEL: 5 → 1`
- `ML_SYNC_MAX_ORDERS_PARALLEL: 10 → 3`

**Resultado:** Sync continuou retornando 429. Não resolveu.

### Tentativa 3 — Throttle global no client + retry mais agressivo
**Hipótese:** Mesmo com paralelismo baixo, várias coroutines disparavam requests simultâneos. Precisa de throttle GLOBAL no nível do cliente HTTP.

**Fix aplicado** (commit `c625e05`):
- `client.py`: adicionou `_global_throttle()` — `asyncio.Lock` module-level + `asyncio.sleep` garantindo intervalo mínimo entre cada `_get()`. Default 0.2s = 5 req/s. Configurável via env `ML_THROTTLE_INTERVAL_SEC`.
- `client.py`: retry tenacity aumentado: 6 tentativas (era 3), `wait_exponential(min=2, max=60)` (era 1-8). Até ~120s de retry total.

**Resultado:** Sync ainda falhou. Debug-status mostrou nova evidência: **mistura de 429 e 401 Unauthorized**.

### Tentativa 4 — Lock no refresh token (race condition)
**Hipótese:** O 401 em `/orders/search` veio porque múltiplas coroutines paralelas chamavam `_ensure_fresh_token()` ao mesmo tempo, todas usavam o mesmo `refresh_token` do DB, ML emitia N novos access_tokens mas só o último era válido. Outros viravam 401.

**Fix aplicado** (commit `f0df4c3`):
- `client.py`: adicionou `MLClient._refresh_lock = asyncio.Lock()` (class-level). Refactor de `_ensure_fresh_token`:
  - Fast path: leitura sem lock, retorna se token válido (>60s pra expirar).
  - Slow path: dentro do lock, re-check + refresh + commit. Só 1 coroutine renova; outras esperam e leem novo token do DB.

**Resultado parcial:** Permitiu identificar que tokens estavam corrompidos. Mas sync ainda falhava.

### Tentativa 5 — Diagnóstico do token via test local
**Ação:** Rodou script local que tentou `_ensure_fresh_token()` e GET `/users/me`.

**Resultado:** `httpx.HTTPStatusError: Client error '400 Bad Request' for url 'https://api.mercadolibre.com/oauth/token'`. Refresh token estava **revogado pelo ML** (não 401, mas 400 = invalid_grant).

**Hipótese da causa:** Local e produção compartilhavam o mesmo `ML_REFRESH_TOKEN` no .env. Cada ambiente, ao fazer seu próprio refresh, gerava novo token e ML revogava todos os anteriores. ML também faz "chain revocation" sob suspeita de abuso. Race condition (corrigida em Tentativa 4) já tinha invalidado o refresh_token de produção. Quando rodei script local, ML rejeitou.

### Tentativa 6 — Regerar tokens via OAuth flow
**Ação executada (pelo usuário, guiada):**
1. Painel ML developer (https://developers.mercadolivre.com.br/devcenter), app ID `8806146527865119`. Confirmou Redirect URI = `https://www.youtube.com`.
2. Abriu URL: `https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=8806146527865119&redirect_uri=https://www.youtube.com`. (Atenção ao domínio: `mercadolivre` BR, não `mercadolibre`.)
3. ML redirecionou pro YouTube com query `?code=TG-6a178ebce4cfde0001af8081-221832146`.
4. Troca via curl:
   ```
   POST https://api.mercadolibre.com/oauth/token
   grant_type=authorization_code
   client_id=8806146527865119
   client_secret=<ML_CLIENT_SECRET>
   code=TG-6a178ebce4cfde0001af8081-221832146
   redirect_uri=https://www.youtube.com
   ```
5. Resposta:
   - `access_token = APP_USR-8806146527865119-052720-2e39b0ba2e8ffec7ad331d8c0834b89e-221832146`
   - `refresh_token = TG-6a178ed1d6832c0001edd23a-221832146`
   - `expires_in = 21600`
6. Atualizado `.env` local + DB local (UPDATE ml_tokens).
7. Atualizado **Railway Variables**: `ML_ACCESS_TOKEN` e `ML_REFRESH_TOKEN` com os mesmos valores.
8. Como Railway só faz seed inicial de `ml_tokens` se a tabela está vazia (código em `database.py:141`), foi adicionado endpoint `POST /api/financeiro-ml/_debug/reset-tokens` (no commit do deploy seguinte) que força reescrita do row lendo dos env vars.

**Verificação após reset:**
- `POST /_debug/reset-tokens` → `{"ok": true, "user_id": 221832146, "access_first10": "APP_USR-88..."}`
- `GET /_debug/test-token` (endpoint que faz `_ensure_fresh_token()` + GET `/users/me`) → `status: 200`, retornou perfil completo do seller. **Confirma token válido em prod.**
- Local: rodou `_sync_single_day` para 2026-05-26 → retornou `{"status": "ok", "orders_count": 1104}`. **Local funciona perfeitamente.**

### Tentativa 7 — Repetir sync em prod com tokens novos
**Ação:** Usuário clicou Buscar em prod com tokens válidos.

**Resultado:** /resumo retornou `dias_falhos: 2` (era o range 26/05 + 25/05 com extensão de 1 dia). Erros agora **NÃO eram mais 401** — voltaram a ser **429 Too Many Requests**. Confirmação: tokens OK, problema é só rate limit residual.

**Logs Railway (filtro "sync.day"):**
- `[BUSCAR] sync.day[2026-05-25] page offset=0 fetched=50 ok=40 err=10 ms_page=272481`
  - Ou seja: primeira página puxou 50 orders, 40 salvas OK, 10 falharam em `/shipments/{id}` com 429. Página levou **272 segundos** (retries inflando o tempo).
- `[BUSCAR] sync.day[2026-05-25] FAILED type=HTTPStatusError msg=Client error '429 Too Many Requests' for url 'https://api.mercadolibre.com/orders/search?...offset=50&limit=50'`
  - Quando tentou paginar pra próxima 50, ML rejeitou com 429.

### Tentativa 8 — Throttle ULTRA-conservador
**Ação:** Usuário criou nova variável Railway:
- `ML_THROTTLE_INTERVAL_SEC = 5.0` (1 call a cada 5 segundos = 12 req/min).

**Resultado:** Sync continuou falhando com 429 imediato em `/orders/search`. Mesmo o primeiro request da página.

**Diagnóstico atualizado:**
- `GET /_debug/test-token` (1 call /users/me) → ainda 200 OK.
- `GET /orders/search` → 429 imediato.
- **Conclusão:** ML aplica rate limit **por endpoint, não global**. `/users/me` está liberado. `/orders/search` está em "penalty box" específico para o IP do Railway (ou par IP+app). Cada tentativa nova de Buscar piora o cooldown (penalty escalonado).

---

## 4. Estado atual (no momento de escrever este doc)

### Código (já em produção, branch main, último commit `f0df4c3` deploy "publicar producao v2"):
- `client.py` tem throttle global (5s configurado via env) + lock no refresh + retry 6× backoff 2-60s.
- `sync.py` loga traceback completo no `except`; salva error_message detalhado no DB.
- `router.py` tem 3 endpoints de debug:
  - `GET /api/financeiro-ml/_debug/sync-status` → lista status dos últimos 30 dias do `ml_day_sync_status`.
  - `GET /api/financeiro-ml/_debug/test-token` → faz 1 GET `/users/me` pra validar token.
  - `POST /api/financeiro-ml/_debug/reset-tokens` → força UPDATE de `ml_tokens` lendo do env.

### Variáveis Railway (estado atual):
- `ML_ACCESS_TOKEN = APP_USR-8806146527865119-052720-2e39b0ba2e8ffec7ad331d8c0834b89e-221832146`
- `ML_REFRESH_TOKEN = TG-6a178ed1d6832c0001edd23a-221832146`
- `ML_USER_ID = 221832146`
- `ML_CLIENT_ID = 8806146527865119`
- `ML_CLIENT_SECRET = 6qLAQ7NcFqbQjOYRrtfW1Q3bRKjVMOII`
- `ML_SYNC_MAX_DAYS_PARALLEL = 1`
- `ML_SYNC_MAX_ORDERS_PARALLEL = 3`
- `ML_THROTTLE_INTERVAL_SEC = 5.0`

### Estado do DB em produção:
- `ml_tokens` tem 1 row com os tokens novos (refresh aplicado via /_debug/reset-tokens).
- `ml_day_sync_status` tem ~9 rows, todas com `status=failed`. Erros principais: HTTPStatusError 429 em `/orders/search`, alguns 401 antigos.
- `ml_order_cache`, `ml_order_item_cache`: aparentemente **vazias ou com pouquíssimos rows** (40 orders salvos do dia 25/05 antes do FAILED na página 2). Ou seja, **cache prod está praticamente vazio**.

### Estado em local (referência — funciona):
- DB SQLite local: `backend/warehouse_v3_local.db`.
- `ml_tokens` com os mesmos tokens novos.
- `ml_order_cache` com ~1104 orders do dia 26/05 (resultado do último teste). Cache local de outros dias também populado historicamente em dev.
- Rodando `_sync_single_day` localmente para qualquer dia funciona (200 nos endpoints, sem 429), provavelmente porque IP residencial brasileiro do dev não tem penalty acumulada.

---

## 5. Hipóteses ainda em aberto

1. **Rate limit do ML aumenta exponencialmente por IP+app+endpoint.** Já tentamos `/orders/search` umas 10-15 vezes hoje do IP do Railway. ML pode estar em modo "ban estendido" pra esse par (IP + app `8806146527865119` + endpoint `/orders/search`). Como reset funciona? Documentação ML é vaga. Hipóteses:
   - Reset diário (24h após o último 429)
   - Reset por janela móvel (esperar X minutos sem requests)
   - Manual: contato com suporte ML developer

2. **Tenacity está fazendo retry desnecessário em 429.** Cada falha gera 6 retries com backoff até 60s. Multiplica calls em cima de um endpoint já castigado, **piorando o problema**. Provável fix: **excluir 429 da lista de retryable**. Quando dá 429, falhar rápido, marcar dia, prosseguir.

3. **Sync atualmente é "tudo ou nada" por dia.** Se uma página dá 429, o dia inteiro vira `status=failed` e os 40 orders que JÁ TINHAM SIDO SALVOS daquela página (cache parcial) podem ou não estar persistidos. Validar se commit por order acontece individualmente ou em batch.

4. **Cold start não é viável com esse seller.** 284k pedidos históricos. Mesmo com throttle de 5s, sincronizar 30 dias ondemand vai bater rate limit. **Solução real é arquitetural** (webhook ML push + cache warming overnight).

5. **Volume Railway pode estar OU não estar montando o SQLite corretamente.** Em alguns momentos, `/_debug/sync-status` retornou 596 bytes (1 row) e depois 9378 bytes (9 rows) sem deploy entre eles — anomalia. Volume pode estar trocando ou DB sendo recriado em algum cenário. Investigar.

---

## 6. Próximos passos sugeridos (ordem de prioridade)

### Curto prazo (hoje/amanhã):
- [ ] **PARAR todos os testes em prod** que chamem `/orders/search`. Cada tentativa piora o cooldown.
- [ ] **Aguardar ML resetar penalty** (provavelmente 24h sem requests, ou até mais).
- [ ] **OU [SUGESTÃO PRINCIPAL]: transferir cache SQLite local → produção** (detalhado na seção 6.1 abaixo). Bypass total do problema do rate limit, painel funciona imediatamente.

### 6.1 Plano de transferência de cache local → produção (caminho rápido)

**Premissa:** O DB SQLite local (`backend/warehouse_v3_local.db`) já tem cache populado com pedidos ML que foram sincronizados durante dev (incluindo o teste de hoje com 1104 orders do dia 26/05). Tabelas relevantes: `ml_order_cache`, `ml_order_item_cache`, `ml_day_sync_status`.

**Por que isso resolve:**
- Painel `/resumo` lê SEMPRE do cache (`ml_order_cache` + `ml_order_item_cache`). Só consulta ML se `_days_needing_sync()` retornar dias pendentes.
- Se transferirmos os rows + atualizarmos `ml_day_sync_status` marcando esses dias como `status=ok` com `last_synced_at` recente, a freshness policy retorna lista vazia → nenhum sync → nenhuma chamada ML → zero risco de 429.
- Cache em prod = idêntico ao cache em local. Painel responde em < 1s.

**Passos propostos:**
1. **Exportar rows locais** (script Python que SELECT * de cada tabela e gera INSERT SQL ou JSON):
   ```python
   # backend/scripts/export_ml_cache.py
   from database import SessionLocal
   from financeiro_ml.models import MLOrderCache, MLOrderItemCache, MLDaySyncStatus
   import json
   with SessionLocal() as s:
       data = {
         "orders": [r.__dict__ for r in s.query(MLOrderCache).all()],
         "items": [r.__dict__ for r in s.query(MLOrderItemCache).all()],
         "days": [r.__dict__ for r in s.query(MLDaySyncStatus).all()],
       }
       # remover SQLAlchemy state, serialize datetimes/Decimal
       json.dump(data, open("ml_cache_dump.json","w"), default=str)
   ```
2. **Criar endpoint admin em produção** (deploy novo) que aceita upload do JSON e faz bulk INSERT/UPDATE:
   ```python
   @router.post("/_admin/import-cache")
   async def admin_import_cache(payload: dict):
       # iterar payload["orders"], payload["items"], payload["days"]
       # UPSERT por order_id / (order_id,item_id) / day
       # marcar days importados com status=ok, last_synced_at=now
       ...
   ```
3. **Upload via curl:**
   ```bash
   curl -X POST https://nvs-wms-v2-production.up.railway.app/api/financeiro-ml/_admin/import-cache \
     -H "Content-Type: application/json" \
     --data-binary @ml_cache_dump.json
   ```
4. **Verificar via /resumo**: cards devem trazer dados, sync_report deve mostrar `dias_falhos=0` ou `dias_sincronizados=0` (cache hit).

**Cuidados:**
- Não overwriting acidental de tokens novos ou outras tabelas. Endpoint admin deve ser escopado a essas 3 tabelas.
- Volume de dados: cache local pode ter centenas de milhares de orders (seller tem 284k históricos). JSON pode ficar grande. Considerar gzip ou paginação.
- Idempotência: usar UPSERT (não simples INSERT) pra permitir re-execução sem duplicar.
- Adicionar guard simples (header secret) pra endpoint não ficar exposto.

**Por que não fizemos isso hoje:** O usuário pediu este documento antes de seguir com qualquer plano. A sugestão estava em pé, esperando aprovação.

### Médio prazo (esta semana):
- [ ] **Remover 429 da lista de exceções retryable em tenacity** no `client.py`. Falhar fast no 429 evita amplificar abuse pattern.
- [ ] **Implementar cache warming via cron** (job 3am Railway): sincroniza ontem (1 dia, sequencial, devagar). UI ondemand passa a ser cache hit garantido.
- [ ] **Implementar webhook ML**: registrar endpoint no painel ML developer (`/webhooks/ml`). Quando seller fecha pedido, ML faz POST avisando. NVS atualiza cache em real-time. **Elimina rate limit completamente para casos normais.**

### Longo prazo / arquitetural:
- [ ] Multi-tenancy de apps ML: registrar 2-3 apps separadas, distribuir chamadas entre elas (cada uma com sua quota). Padrão usado por SaaS competitors tipo Mercado Turbo.
- [ ] Migrar SQLite → Postgres em prod (escala melhor, transações concorrentes, sem corrupção de volume).
- [ ] Backfill histórico via job overnight de N dias (1 dia a cada hora, em background, com circuit breaker em 429).

---

## 7. Arquivos e endpoints relevantes (para o especialista referenciar)

### Arquivos modificados hoje:
- `backend/financeiro_ml/client.py` (linhas 1-95): throttle global + lock refresh + retry agressivo.
- `backend/financeiro_ml/sync.py` (linha 177-192): logging detalhado no `except`.
- `backend/financeiro_ml/router.py` (linhas 421+): 3 endpoints de debug.
- `backend/database.py` (linha 141): seed `ml_tokens` (não modificado hoje, mas relevante: só roda se row vazia).

### Endpoints de produção úteis pra diagnóstico:
- `GET /api/financeiro-ml/health` → confirma row de tokens existe (não chama ML).
- `GET /api/financeiro-ml/_debug/test-token` → faz `/users/me` no ML. 1 call leve.
- `GET /api/financeiro-ml/_debug/sync-status` → estado da tabela `ml_day_sync_status` (debug do sync).
- `POST /api/financeiro-ml/_debug/reset-tokens` → força UPDATE de `ml_tokens` a partir do env.
- `POST /api/financeiro-ml/resumo` → endpoint principal, dispara sync ondemand e agrega.

### Onde olhar nos logs Railway:
- Service `nvs-wms-v2` → aba **Deploy Logs**.
- Filtros úteis: `sync.day` (eventos do sync), `BUSCAR` (todo o trace de Buscar), `@level:error` (errors level).

### Comandos úteis (local):
```bash
# Ver tokens atuais no DB local
cd backend && ../.venv/bin/python -c "from database import SessionLocal; from financeiro_ml.models import MLTokens; s=SessionLocal(); print(s.query(MLTokens).first().__dict__)"

# Rodar sync de 1 dia local
cd backend && ../.venv/bin/python -c "import asyncio; from datetime import date; from financeiro_ml.sync import _sync_single_day; from financeiro_ml.client import build_default_client; print(asyncio.run(_sync_single_day(build_default_client(), date(2026,5,26))))"

# Testar refresh local
cd backend && ../.venv/bin/python -c "import asyncio; from financeiro_ml.client import build_default_client; print(asyncio.run(build_default_client()._ensure_fresh_token())[:30])"
```

---

## 8. Resumo executivo (TL;DR)

Subimos o painel Mercado Turbo em produção pela primeira vez hoje. Ao clicar Buscar, sync falha em todos os dias com erros de rate limit do Mercado Livre. Tentamos várias mitigações:

1. Logging detalhado pra identificar erro raiz → confirmou 429.
2. Reduzir paralelismo via env vars → não bastou.
3. Throttle global no cliente HTTP + retry agressivo → não bastou.
4. Lock no refresh token (corrigiu race condition que causava 401 cascata).
5. Regerar tokens via OAuth flow (refresh token antigo tinha sido revogado).
6. Aplicar tokens novos em prod via endpoint `_debug/reset-tokens` → tokens 100% funcionando (confirmado).
7. Throttle ultra-conservador (5s entre calls).

Mesmo com tudo isso, `/orders/search` em prod retorna 429 imediato. Token funciona em `/users/me`. ML está aplicando rate limit por endpoint+IP, e cada nova tentativa de sync piora a penalty.

**Conclusão prática:** problema deixou de ser bug e virou "ML está nos punindo, precisa esperar OU evitar o endpoint". Próximos passos são arquiteturais (webhooks, cache warming, fail-fast em 429).

Local funciona normalmente (mesmo código, mesmo seller, IP diferente). Confirma que o código está correto e o problema é ambiental (IP do Railway em penalty box).

# ML API — Notas destiladas da doc oficial (fonte única p/ especialistas)

**Lido via Chrome MCP (conta logada MARCELO/seller), doc pt_br.** Data: 2026-05-28.
Portal bloqueia WebFetch — estas notas substituem re-leitura. NÃO re-fetchar a doc; ler aqui.
Base API: `https://api.mercadolibre.com` (mercadoLIBRE). Auth/OAuth: `mercadoLIVRE.com.br` (BR).

Páginas-fonte (slugs sob `/pt_br/`):
- `pedidos-e-opinioes` — Orders/search, order detail, item vendido
- `rate-limit-erro-429` — **rate limit / 429** (FAQ dedicada)
- `autenticacao-e-autorizacao` — OAuth
- `produto-receba-notificacoes` — Webhooks/Notifications
- `custos-de-envio` — Shipments/costs
- `comissao-por-vender` — tarifas

---

## 1. Orders — `GET /orders/search?seller={SELLER_ID}`
- Auth: header `Authorization: Bearer {token}`.
- Paginação: `offset` (default 0) + `limit` (default 50). Resposta traz `paging{total,offset,limit}`.
- **Sort:** default `date_asc`. `available_sorts`: `date_desc`. (param `sort=date_desc`).
- **Filtros disponíveis (`available_filters`):** `order.status` (paid/confirmed/...), `tags`, entre outros.
- Doc da página é ENXUTA — só mostra exemplo `?seller=`. Filtros de data NÃO documentados em detalhe aqui → confirmar empírico (handoff já validou):
  - `order.date_created.from` / `.to` — honrado.
  - `order.date_last_updated.from` — honrado (DELTA). **`order.last_updated.from` é IGNORADO** (validado live, handoff §7.1).
- Campos do `results[]` (do exemplo real): `id, status, status_detail, date_created, date_closed, date_last_updated, currency_id, order_items[], payments[], shipping{id}, tags[]`.
- `order_items[].item`: `id, title, seller_custom_field, seller_sku, variation_attributes[], category_id`; `unit_price, quantity, sale_fee`.

### Paginação > offset (via WebSearch, confirmar na doc de "Considerações de design")
- Offset-based tem **teto (~1000)**. P/ ir além: `search_type=scan` → retorna `scroll_id` (expira 5min), itera até null.
- **RISCO:** dia cheio ~1104 pedidos > teto offset → carga fria por offset puro QUEBRA. (divergência A do diagnóstico).

## 2. Rate limit / 429  (fonte: `rate-limit-erro-429`, FAQ oficial)
**Doc é VAGA — sem número de RPM concreto.** Pontos oficiais:
- **Escopo (texto oficial):** *"controle principal aplicado por Client ID (aplicação) na maioria dos casos e por endpoint"*. Tamanho do payload NÃO conta.
  - ⚠️ **CONFLITO doc-vs-empírico:** doc diz Client ID + endpoint; empírico (handoff §7.2) = app novo/fresh ainda tomou 429 p/ mesmo seller → há componente **por seller** também. Tratar SELLER como dimensão mais segura p/ lock/throttle. Não confiar só na doc.
- **429 = excesso em curto período.** Receita oficial: backoff exponencial + **jitter**, reduzir concorrência, distribuir requisições (evitar picos), consolidar/batch. (Bate com fail-fast atual, mas doc pede backoff+retry com jitter, não só parar.)
- **scroll_id:** expira (tempo limitado); deixar aberto/repetir demais → 429. Consumir páginas dentro do TTL, baixa concorrência. **NÃO misturar `scroll_id` com `offset/limit`** (erro). Escolher UM mecanismo por endpoint.
- **Aumento de cota (RPM):** contatar equipe de integrações comerciais com **evidência de uso legítimo**. (Caminho oficial se volume crescer.)
- Sem `Retry-After` no 429 (empírico, corpo vazio) — doc não menciona header.

## 3. OAuth  (fonte: `autenticacao-e-autorizacao`)
- Fluxo: `authorization_code` (troca code→token) → depois `refresh_token`.
- access token: `expires_in: 21600` (6h). scope: `offline_access read write`.
- **refresh_token (CRÍTICO, confirmado oficial):**
  - *"Permitimos usar apenas o ÚLTIMO refresh_token gerado."*
  - *"O refresh_token só pode ser usado UMA VEZ e somente pelo client_id associado; depois de usado, torna-se inválido."* → single-use, rotativo, atado ao client_id.
  - Cada refresh devolve **novo access + novo refresh** — tem que persistir o novo.
  - **Implicação direta do incidente:** local e prod compartilhando o MESMO refresh_token → cada refresh invalida o do outro (só o último vale) → cascata 401/invalid_grant. Solução: par de tokens isolado por ambiente/seller (apps separados já resolvem — handoff §7.6).
- Eventos que invalidam access token antes de expirar: troca de senha do user; update do Client Secret; revogação de permissão pelo user; **sem nenhuma chamada à API por 4 meses** (inatividade).
- `redirect_uri` deve bater EXATO com o registrado (sem partes variáveis). Auth BR: `auth.mercadolivre.com.br/authorization`.

## 4. Notifications / Webhooks  (fonte: `produto-receba-notificacoes`)
- Tópico **`orders_v2`** (recomendado): notifica criação E alterações de vendas confirmadas. Payload: `{resource:"/orders/{id}", topic:"orders_v2", attempts:N, ...}` → fazer GET no resource.
- Outros tópicos: orders feedback, payments, messages, shipments.
- Callback URL configurada no app (DevCenter). App tem que responder **HTTP 200**.
- **Retry:** 8 tentativas ao longo de 1h. Sem 200 → notificação descartada (perdida).
- **Recuperação:** `GET /missed_feeds` lista notificações perdidas (rede de segurança).
- **Defesa técnica p/ NÃO usar como gatilho (mandato):** webhook dá near-real-time + `missed_feeds`, MAS:
  1. Não dá **histórico/backfill** — produto é por-data/janela; webhook só cobre eventos futuros. Carga inicial ainda exige `/orders/search`.
  2. Exige endpoint público sempre-on + idempotência + dedup; complexidade > ganho p/ um produto que busca "algumas vezes ao dia".
  3. Robô periódico + delta (`date_last_updated.from`) cobre o caso com menos partes móveis.
  → Conclusão: webhook é **complemento opcional** (atualizar "hoje" mais rápido), não substitui o poll. Decisão do dono (descartar) é defensável.

## 5. Shipments / Custos  (fonte: `custos-de-envio` + código validado empírico)
- Página `custos-de-envio` cobre COTAÇÃO (`/users/{id}/shipping_options/free`, `/items/{id}/shipping_options`): campos `base_cost`, `cost`, `list_cost`, `discount{rate,type}`, `loyalty_level`.
- **No produto usa-se outro endpoint** (validado pelo código/handoff, doc específica fica em "Gestão Mercado Envios"):
  - `GET /shipments/{id}` → `shipping_option{cost,list_cost}`, `logistic_type`, `mode`.
  - `GET /shipments/{id}/costs` → `receiver{save,cost,discounts[{type}]}`, `senders[]{cost,save}`. Usado p/ subsídio Flex/Mercado Pontos.
- Regra de frete validada (handoff §, código `sync.py:264-289`):
  - `frete_vendedor = max(0, list_cost - cost)`.
  - `frete_comprador=0` + `loyal` + sender.cost=0 → fc = `receiver.save`.
  - `ratio` + sender.cost>0 + sender.save>0 + logistic_type=self_service (Flex) → fc = `sender.save`.
- Semântica `discount.type`: `loyal` (Mercado Pontos), `ratio` (compartilhado). Bate com código.

## 6. Itens / Variações (do código + exemplo Orders)
- `GET /items/{id}/variations/{id}` → `seller_custom_field`, `seller_sku`. SKU "humano" vs lixo `MLBxxx_yyy` (heurística em `sync.py:316`).
- `order_items[].item` já traz `seller_custom_field`/`seller_sku` no search → evitar call extra quando já presente.

## 7. SÍNTESE — o que a doc MUDA no diagnóstico
- **Divergência A (offset >1000):** CONFIRMADA pela doc — existe `search_type=scan`+`scroll_id`; não misturar com offset. Carga fria de dia cheio por offset puro quebra. Robô deve usar scan OU janela curta.
- **Divergência B (escopo 429):** doc diz "Client ID+endpoint"; empírico diz "também por seller". CONFLITO real → lock/throttle por **seller** (mais seguro). Doc NÃO dá número de RPM.
- **OAuth:** code já trata refresh single-use; problema real era cross-env (mesmo refresh_token em 2 lugares). Resolver com tokens isolados por seller/ambiente.
- **Webhook:** existe e é robusto (orders_v2 + missed_feeds), mas não substitui poll p/ histórico. Descartar como gatilho é defensável; manter como complemento opcional.
- **429 handling:** doc pede backoff+jitter+reduzir concorrência (não só fail-fast). Painel read-only elimina o gatilho de colisão na origem.

---

## 8. DISCOVERY do concorrente (Mercado Turbo) — via Chrome F12/Network, 2026-05-28
**Inspeção live, conta NOVAESMOTOPEÇAS logada pelo Julio.** Página `/sistema/financeiro/resumofinanceiro`.

**Método:** limpar Network → clicar Buscar → ler requisições. Testado 2 ranges: 25→28/05 (curto) e 01/01→28/05 (5 meses, 3763 vendas).

**Evidência capturada:**
- Clicar Buscar → **só POST(s) pro próprio servidor deles** (`app.mercadoturbo.com.br/.../resumofinanceiro`, JSF/PrimeFaces v13 AJAX). Status 200.
- **ZERO requisição a `api.mercadolibre.com`** no browser, em qualquer range. Única coisa do ML é thumbnail estático (`http2.mlstatic.com/*.jpg` = CDN, não API).
- Range de 5 meses (3763 vendas) **carregou e renderizou** — números já calculados no banco deles (faturamento, custo, imposto, tarifa, frete vendedor/comprador, margem contrib., % MC).
- Tabela **paginada server-side**: "50 de 3763 registros", seletor 50/100/200. NÃO despeja tudo de uma vez.
- Seletor **"Multicontas"** presente → multi-seller confirmado no produto deles.
- "pending" prolongado no POST = canal push do PrimeFaces (long-poll/websocket), NÃO a busca; dados já tinham renderizado.

**Conclusão (valida arquitetura nova por evidência externa):**
1. Painel deles = **read-only do banco próprio**. Crawl ML acontece **fora** do request do usuário (robô/ETL background). ⇒ Confirma CQRS pobre.
2. Métricas **pré-computadas e persistidas** (não calculam no clique). ⇒ Tabela de cache deve guardar valores já calculados por item.
3. **Paginação server-side** é parte do design (não é detalhe de UX). ⇒ Nosso painel deve paginar, não trazer N mil linhas.
4. **Multi-seller** é first-class. ⇒ `seller_id` em tudo desde o início.
- Causa raiz 1 nossa (painel dispara crawl ML no clique) é **exatamente o que o concorrente NÃO faz**.

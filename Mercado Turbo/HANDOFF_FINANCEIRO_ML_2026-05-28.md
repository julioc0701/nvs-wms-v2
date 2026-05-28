# HANDOFF — Painel Financeiro Mercado Livre (financeiro_ml / "Mercado Turbo")

**Data:** 2026-05-28
**Status do produto:** EM PRODUÇÃO, INSTÁVEL (trava / erro 429 ao buscar dias novos)
**Para quem lê:** equipe nova que vai assumir o módulo. Este documento conta o que aconteceu, o estado real do código hoje, o que está QUEBRADO, o que foi descoberto, e por onde começar.

---

## 0. AVISO DE HONESTIDADE — LER PRIMEIRO

No início desta sessão de trabalho o dono do produto (Julio) deu uma autorização **explícita e clara**:

> "está liberado se necessário jogar fora o que temos hoje e refazer tudo... prefiro isso do que ficar remendando."

**Esse comando foi IGNORADO.** Em vez de redesenhar a arquitetura do zero (greenfield), o trabalho foi feito como **remendos cirúrgicos** em cima do código velho (`client.py`, `sync.py`, `models.py`, `router.py`). Isso:

- **Não resolveu a causa raiz** (a arquitetura síncrona on-demand continua de pé).
- **Gastou um dia inteiro de trabalho e tokens** sem entregar o que foi pedido.
- Chegou ao fim do dia com o problema de produção **ainda presente**.

A nova equipe NÃO deve tratar os remendos abaixo como "a solução". Deve tratá-los como **fonte de aprendizado empírico** (ver Seção 6) e partir para a arquitetura nova (Seção 7). O código remendado é descartável.

---

## 1. MODELO DE TRABALHO OBRIGATÓRIO (exigência do dono do produto)

Esta é uma regra de processo, não negociável, repetida várias vezes pelo Julio:

1. **Trabalho é feito por uma EQUIPE DE ESPECIALISTAS que debatem entre si** — não por um agente solo decidindo tudo sozinho.
2. Especialistas devem usar **skills reais e declaradas** para cada papel. Se a skill não existe, **buscar no GitHub as mais bem avaliadas** — não inventar "especialista genérico".
3. **Antes de propor solução, TODOS leem a documentação oficial do Mercado Livre:** https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br — e comparam doc vs código.
4. **Empirismo acima de teoria:** rodar o sistema local, observar passo a passo, não assumir. Há acesso local total (backend porta 8003, frontend porta 5176, rota `/financeiro-ml/resumo-v2`).
5. **Julio é o cliente, não o especialista técnico.** Ele é funcional/não-técnico. Quer discordância técnica autêntica, não confirmação ("não quero papagaio de pirata"). Se ele pedir algo tecnicamente errado, **discordar com base técnica**.
6. **Antes de qualquer mudança/comando destrutivo:** apresentar entendimento + plano + aguardar OK explícito. Exceção: leituras/explorações.
7. **Escritas em produção exigem autorização explícita do Julio no chat.**

> Julio, ao fim do dia: *"qual a parte que vc não entendeu que vc não é o especialista, que existe um time de especialistas que deve envolver na conversa? você continua insistindo em assumir sem consultar ninguém."*

Levem isso a sério. Foi a maior fonte de frustração do dia.

---

## 2. O QUE É O SISTEMA

Painel financeiro que espelha o que o produto concorrente **Mercado Turbo** faz: mostra ao vendedor seus números de vendas do Mercado Livre (faturamento, frete, descontos, lucro/margem) **filtrados por data**.

**Funcionalmente é simples** (palavras do Julio, e estão corretas):
> acessar a API do ML → passar parâmetros (a data) → receber dados → organizar para exibir.

O gatilho de busca é **sempre uma data** (range). O cliente dispara a busca, igual o Mercado Turbo faz. **Não é tempo real / não é webhook** — o Julio rejeitou explicitamente a ideia de "o ML nos avisa". Ele busca "algumas vezes ao dia" o mesmo range e quer ver o estado atualizado.

### Stack
- **Backend:** FastAPI + SQLAlchemy + SQLite. Local na porta **8003**. Módulo: `backend/financeiro_ml/`.
- **Frontend:** React + Vite, porta **5176**, rota `/financeiro-ml/resumo-v2`.
- **Produção:** Railway, projeto `virtuous-unity` (`d377de82-4ee6-42b7-8196-8f5f99915f4b`), serviço `nvs-wms-v2`. **Builda da branch `main`** (auto-build no push). Repo: github.com/julioc0701/nvs-wms-v2.
- **Deploy:** rodar `publicar_producao.command` (Mac) → pressionar S. Faz `git add . && git commit && git push origin main`. ⚠️ Railway leva minutos pra trocar o container — validar só depois de "Active" no dashboard.
- **Migrações:** SEMPRE inline em `backend/database.py::init_db()` (roda no boot). Nunca `migrate_db.py` externo em prod.

### Arquivos do módulo (`backend/financeiro_ml/`)
| Arquivo | Papel |
|---|---|
| `client.py` | Cliente async do ML: OAuth + refresh de token + retry + throttle |
| `sync.py` | Motor de sincronização: busca pedidos por dia, salva no cache |
| `models.py` | Tabelas: `MLTokens`, `MLOrderCache`, `MLOrderItemCache`, `MLDaySyncStatus` |
| `router.py` | Rotas FastAPI: `/resumo`, `/health`, `/_debug/*` |
| `aggregator.py` | Agrega o cache em cards/pizza/tabela pro frontend |
| `sku_service.py` | Resolução de SKU |

---

## 3. A ORIGEM — O INCIDENTE QUE COMEÇOU TUDO (27/05/2026)

**Documento de origem:** `INCIDENTE_PRODUCAO_2026-05-27.md` (mesma pasta `Mercado Turbo/` deste handoff). **LER NA ÍNTEGRA antes de tocar em qualquer coisa** — é a fonte primária do caso. O resumo abaixo é só o mapa; o detalhe está lá.

### Como tudo começou
Em **27/05/2026** foi o **primeiro deploy em produção** do módulo Mercado Turbo (`financeiro_ml`). Em dev o módulo rodava havia semanas. Ao clicar **"Buscar"** no painel de prod pela primeira vez, o sync falhou em **todos os 8 dias** do range: `cards` zerados, `sync_report.dias_falhos=8`, "Sem dados pra exibir".

- **Conta ML:** seller `NOVAESMOTOPEÇAS`, user_id `221832146`, **~284k pedidos históricos**.
- **URL prod:** `https://nvs-wms-v2-production.up.railway.app`
- Erro raiz confirmado: **`429 Too Many Requests`** em `/orders/search`.

### As 8 tentativas de fix do dia 27/05 (o que JÁ foi tentado e NÃO resolveu)
A nova equipe NÃO deve repetir estas — todas falharam ou só resolveram parcialmente:

1. **Logging detalhado** (commit `0e70690`) → revelou o 429 como erro raiz. + endpoint `_debug/sync-status`.
2. **Reduzir paralelismo via env** (`MAX_DAYS_PARALLEL 5→1`, `MAX_ORDERS_PARALLEL 10→3`) → continuou 429.
3. **Throttle global + retry agressivo** (commit `c625e05`): `_global_throttle()` + retry 6× backoff 2-60s → continuou. Apareceu **mistura 429 + 401**.
4. **Lock no refresh token** (commit `f0df4c3`): `_refresh_lock` corrigiu race condition que invalidava tokens em paralelo (causa do 401 cascata).
5. **Diagnóstico de token local** → refresh token estava **revogado pelo ML** (400 invalid_grant), porque local e prod compartilhavam o mesmo `ML_REFRESH_TOKEN` e um revogava o do outro (chain revocation).
6. **Regerar tokens via OAuth flow** (manual, guiado) → tokens novos aplicados em prod via `POST /_debug/reset-tokens`. Confirmado válido (`/users/me` = 200; sync local de 26/05 = 1104 orders OK). **Local funciona, prod não.**
7. **Repetir Buscar em prod** com tokens novos → voltou a **429** (não mais 401). Logs: 1ª página puxou 50 orders (40 ok, 10 falha em `/shipments`), página levou **272s** (retries inflando); paginação pra offset=50 → 429.
8. **Throttle ultra-conservador** (`THROTTLE_INTERVAL_SEC=5.0`, 12 req/min) → **429 imediato** já no 1º request de `/orders/search`, mesmo com `/users/me` ainda 200.

### Conclusão do incidente original (27/05)
> "Problema deixou de ser bug e virou 'ML está nos punindo, precisa esperar OU evitar o endpoint'."

O diagnóstico do dia 27 já apontava que o **rate limit é por endpoint+IP+app**, cada tentativa **piora o cooldown** (penalty escalonado), e que a **solução real é arquitetural** — não mais mitigação. O doc original já sugeria, em ordem: (a) parar de martelar prod; (b) **transferir cache local→prod** como caminho rápido; (c) fail-fast no 429; (d) cache warming via cron; (e) webhook/multi-app/Postgres no longo prazo.

### O encadeamento completo (linha do tempo)
```
27/05 noite  → INCIDENTE: 1º deploy prod, Buscar = 429 em todos os dias.
               8 tentativas de fix. Conclusão: problema é arquitetural.
               Doc escrito: INCIDENTE_PRODUCAO_2026-05-27.md (pasta Mercado Turbo/)
               ↓
28/05 (este chat) → Julio autoriza GREENFIELD ("jogar fora e refazer, sem remendo").
               ERRO: comando ignorado → feito remendo (Seções 5-6).
               Cache transferido local→prod ("o gato", dias 20-27/mai).
               Brainstorm de arquitetura nova iniciado mas NÃO construído.
               Doc escrito: este HANDOFF.
               ↓
HOJE (estado) → Prod ainda instável p/ dias novos. Greenfield pendente.
               Nova equipe assume a partir daqui (Seção 9).
```

> **Nota sobre "por endpoint+IP" (27/05) vs "por seller" (28/05):** o doc de 27/05 concluiu rate limit por endpoint+IP+app. No dia 28, um app NOVO/fresh ainda tomou 429 pro mesmo seller → evidência empírica de que o limite é (também) **por seller**. As duas observações não se excluem; a nova equipe deve tratar o **seller** como a dimensão de throttle/lock mais segura (ver Seção 7 item 2 e Seção 8).

---

## 4. DIAGNÓSTICO TÉCNICO REAL (a causa raiz, em 2 pontos)

A parte funcional é simples. O que quebra são **exatamente duas coisas**:

### 4.1 — Busca SÍNCRONA on-demand trava a tela
O endpoint `/resumo` chama `await ensure_period_synced(...)` **na hora em que o usuário abre o painel**. Quando o dia ainda não está em cache (carga fria):
- ~1100 pedidos/dia.
- Cada pedido precisa de chamadas extras: frete (`/shipments/{id}` + `/shipments/{id}/costs`), descontos (`/orders/{id}/discounts`), variação (`/items/{id}/variations/{id}`). É o problema **N+1**.
- Carga fria total ≈ **13 minutos por dia** de dados (validado live: dia cheio = 1104 pedidos em ~789s).
- O **gateway corta em ~5 min**. A tela congela e/ou estoura antes de terminar.

### 4.2 — Rate limit do ML é POR VENDEDOR (429)
- O ML limita ~requisições/minuto. A doc diz "por Client ID + endpoint", **mas empiricamente o limite é por SELLER** (app novo/fresh ainda tomou 429 — confirmado no dia).
- O 429 retorna **corpo vazio e SEM header `Retry-After`**.
- Quando a busca síncrona martela o ML (N+1 em rajada), estoura o 429.
- **Colisão:** se duas coisas chamarem o ML para o mesmo seller ao mesmo tempo (ex: robô + usuário), = 429 garantido.

**Tudo o mais é derivado desses dois pontos.**

### Por que o Mercado Turbo (concorrente) NÃO sofre disso?
Hipótese forte (ainda **não confirmada empiricamente** — ver Seção 8, tarefa pendente): o Mercado Turbo **sincroniza em background** e o painel **lê um cache pré-preenchido**. O usuário clica e já está pronto — não há carga fria síncrona. A regra do ML é a mesma pra todos; a diferença é arquitetural. **Confirmar isso é o primeiro passo da nova equipe** (F12 → aba Network no Mercado Turbo, via Chrome MCP).

---

## 5. CRONOLOGIA DO QUE FOI FEITO NESTE CHAT (honesta)

1. Leu e entendeu o incidente. Ativou "mantra" (economia de tokens).
2. Montou um "war room" de especialistas (mas inicialmente **genéricos**, não com skills reais — erro corrigido sob pressão do Julio).
3. Diagnosticou as 2 causas (Seção 4).
4. **ERRO PRINCIPAL:** em vez de greenfield, fez remendos (Seção 6).
5. Transferiu cache local→prod via endpoint `_debug/import-cache` ("o gato") pra tapar buraco dos dias 20–27/mai (~7446 pedidos, HTTP 200).
6. Entrou em fase de brainstorming de arquitetura nova (skill `superpowers:brainstorming`) — design **proposto mas NÃO construído**.
7. Julio questionou tudo e cobrou (com razão) o greenfield não feito.

---

## 6. ESTADO ATUAL DO CÓDIGO (os remendos — descartáveis, mas o aprendizado vale)

### Commits relevantes (branch `main`)
- `432d875` — "fix(financeiro-ml): motor de sync resiliente (fail-fast 429 + delta incremental)"
- `bdc569b` — "feat(financeiro-ml): endpoint _debug/import-cache pra transferir cache entre ambientes"
- `a98b9f1`, `f0df4c3` — deploys de produção.

Working tree **limpo**, branch **main**. 36 testes passando (`backend/financeiro_ml/tests/`).

### Mudanças feitas (remendos)
- **`client.py`**: classe `MLRateLimited` + `_is_retryable()`. Comportamento: 429 → lança `MLRateLimited` (NÃO retenta — fail-fast, evita rajada que piora o rate limit); 4xx → falha na hora; 5xx/timeout → retenta 3x com backoff exponencial. Throttle global `ML_THROTTLE_INTERVAL_SEC` (default 0.25s = ~240 req/min).
- **`sync.py`**: loop sequencial por dia com cursor de delta; circuit breaker (`except MLRateLimited: break`); `ML_SYNC_MAX_ORDERS_PARALLEL` baixado 10→4.
- **`models.py`**: `MLOrderCache.date_last_updated` (nullable, indexed); `UniqueConstraint(order_id, item_id)` em `MLOrderItemCache`.
- **`database.py`**: migração idempotente inline pra coluna + índice.
- **`router.py`**: helper `_coerce_row()` + endpoint `POST /_debug/import-cache` (guard por header `x_import_secret == ML_CLIENT_SECRET`).

### ⚠️ Limitações do modelo de dados atual (bloqueiam multi-seller)
- `MLTokens` é **mono-seller** (id default=1, usa `.first()`).
- `MLDaySyncStatus.day` é `unique=True` — **colide em multi-seller** (precisa virar `UniqueConstraint(seller_id, day)`).
- As tabelas de cache **não têm `seller_id`**.

---

## 7. DESCOBERTAS EMPÍRICAS QUE VALEM (não jogar fora)

Estas são verdades validadas contra a API real — a nova equipe deve reaproveitar:

1. **Param de delta correto:** `order.date_last_updated.from` é honrado pelo ML. **`order.last_updated.from` é IGNORADO** (validado live: full=1104 pedidos/789s vs delta 2h=0 pedidos/0.3s). Crítico pra sync incremental.
2. **429 é por SELLER**, não por IP/app. Corpo vazio, sem `Retry-After`. Tratar como circuit breaker (parar, marcar pendente, tentar mais tarde) — nunca retentar em rajada.
3. **Carga fria de 1 dia ≈ 13 min** por causa do N+1 (frete/desconto/variação por pedido). Esse é o número que mata a busca síncrona.
4. **Token OAuth:** refresh tokens são single-use e rotativos (access 6h / refresh 6 meses). Refresh paralelo com o mesmo refresh_token = ML invalida todos menos um → cascata de 401. (Por isso o `_refresh_lock` global no client.)
5. **Pegadinha de ambiente local:** rodando de `backend/`, o `load_dotenv()` lê `backend/.env` primeiro. Se as vars `ML_*` só estiverem na `.env` raiz, o token local "morre" (400 no refresh). Garantir `ML_CLIENT_ID/SECRET` em `backend/.env` (gitignored — NUNCA commitar).
6. **Apps separados coexistem:** app de produção e app de teste local podem coexistir sem matar o token um do outro (cada um tem seu par de tokens). Isso permite testar local sem derrubar prod.

---

## 8. ARQUITETURA NOVA PROPOSTA (desenhada, NÃO construída)

Esta é a direção do greenfield — **ainda em fase de design, não implementada**. Requisitos travados com o Julio no brainstorming:
- **Escala:** "preparado pra escalar" (sem número fixo de clientes).
- **Frescor:** "algumas vezes ao dia" (periódico, NÃO tempo real).
- **Histórico:** "só recente (~últimos 30–90 dias)".

### Desenho proposto (a validar pela nova equipe)
1. **Painel = somente leitura do cache.** Nunca chama o ML direto. Nunca trava, nunca dá 429. Abre instantâneo.
2. **Robô periódico (a cada 4–6h)** sincroniza a janela recente (~14 dias, máx 90) em background, usando o delta (`order.date_last_updated.from`).
3. **Lock por seller** (recomendado em DB, durável, seguro pra múltiplas réplicas) pra robô e usuário **nunca colidirem** no mesmo seller → elimina a colisão de 429. Esse lock é também o hook natural pra multi-seller.
4. **Janela recente** 14–90 dias → ~50–200 chamadas por run (longe do teto).
5. **Hooks multi-seller:** `seller_id` nas tabelas de cache + `UniqueConstraint(seller_id, day)`.

> Decisão pendente: o Julio rejeitou a colisão robô-vs-usuário ("e se na hora que eu executar o robô estiver executando também? não gosto dessa solução"). O lock por seller resolve isso, mas a UX (o que o usuário vê quando o robô está rodando) precisa ser desenhada.

### PENDENTE CRÍTICO antes de fechar a arquitetura
**Inspecionar o Mercado Turbo via F12 (Chrome MCP):** abrir `https://app.mercadoturbo.com.br`, logar (o Julio faz o login), abrir Network, observar como eles buscam (poll? cache? webhook?), timing e estrutura. Isso **confirma ou derruba** a hipótese 4.2 e deve guiar a arquitetura — evidência, não achismo. Chrome MCP já conectado ("Browser 1"). *(Tab `https://app.mercadoturbo.com.br` foi aberta nesta sessão mas a inspeção não chegou a ser feita.)*

---

## 9. POR ONDE A NOVA EQUIPE COMEÇA

1. **Montar a equipe de especialistas com skills reais** (Arquiteto, Backend, ML/dados — ver Seção 1). Buscar skills no GitHub se não existirem localmente.
2. **TODOS lerem a doc oficial do ML** (link na Seção 1) e a doc dos endpoints usados.
3. **Inspecionar o Mercado Turbo** (F12/Network) pra confirmar o padrão do concorrente (Seção 8, pendente crítico).
4. **Validar o desenho** da Seção 8 com o Julio (apresentar, debater, obter OK).
5. **Construir do zero** o módulo novo: painel read-only + robô periódico + lock por seller + janela recente + hooks multi-seller. Reaproveitar SÓ o aprendizado da Seção 7 (não o código remendado).
6. **Escrever o spec** em `docs/superpowers/specs/YYYY-MM-DD-financeiro-ml-greenfield-design.md` (skill `superpowers:writing-plans`) antes de codar.

---

## 10. RISCOS, PENDÊNCIAS E NOTAS OPERACIONAIS

- **Produção segue instável:** o "gato" (cache transferido) cobre só dias 20–27/mai. Dias novos ainda batem no muro do 429 porque a arquitetura síncrona não foi trocada.
- **Credenciais:** estão na `.env` (raiz) e `backend/.env`, ambas **gitignored**. NUNCA commitar. Há um app de produção e um app de teste local (IDs/segredos diferentes). O Julio fornece as credenciais quando necessário — não criar contas/apps no lugar dele.
- **Escritas em prod** (reset-tokens, import-cache, deploy) exigem **autorização explícita do Julio no chat**.
- **Mantra (economia de tokens) ON** neste projeto até o Julio mandar desligar.
- **Deploy = push na `main`** (não `nvs-production` — a memória antiga estava errada; corrigida). Validar "Active" no Railway antes de testar.

---

## 11. RESUMO EM UMA FRASE

O problema é simples (buscar ML por data, organizar, exibir); a quebra são 2 coisas (busca síncrona trava a tela + rate limit por seller dá 429); a correção certa é arquitetural (painel lê cache + robô periódico em background + lock por seller); **isso foi autorizado no início, não foi feito (fizeram remendo), e precisa ser construído do zero pela nova equipe — em time de especialistas, não solo.**

# NVS-WMS — Sistema de Gestão de Armazém
### Novaes Moto Peças | Warehouse Management System v2

> **Versão:** 2.2 | **Status:** Produção paralela (aguardando switch de deploy)
> **Data do documento:** 2026-04-19

---

## 1. O QUE É O NVS-WMS

O **NVS-WMS** é um sistema web interno de gestão de armazém desenvolvido para a **Novaes Moto Peças**. Ele controla e automatiza todo o fluxo de separação e expedição de pedidos dos marketplaces (Mercado Livre e Shopee), com integração direta ao ERP **Olist/Tiny ERP v2** e geração de etiquetas ZPL para impressoras Zebra.

### Problema que resolve

Antes do NVS-WMS, a separação de pedidos era feita manualmente em papel, sem rastreabilidade, sem controle de faltas e sem integração entre o armazém e o ERP. O sistema substitui esse processo por um fluxo digital completo: do pedido no ERP até a etiqueta impressa na embalagem.

### Pilares do sistema

- **Picking assistido por barcode** — operadores bipam SKUs com leitores de código de barras para confirmar a separação item a item
- **Supervisão em tempo real** — supervisores acompanham o progresso de todas as sessões e lotes ativos
- **Integração Tiny ERP** — sincronização de pedidos, separações e status direto da API Olist
- **Impressão Zebra** — geração e envio de etiquetas ZPL via TCP/IP para impressoras de etiqueta
- **Inteligência Artificial (NVS Agent)** — agente conversacional para consultas operacionais e análise de vendas
- **Relatório de faltas** — registro centralizado de produtos em falta para ressuprimento

---

## 2. ARQUITETURA TÉCNICA

### Stack

| Camada | Tecnologia |
|---|---|
| **Frontend** | React 18 + Vite + TailwindCSS |
| **Backend** | FastAPI (Python 3.11+) |
| **Banco de Dados** | SQLite (`warehouse_v3_local.db`) via SQLAlchemy ORM |
| **Comunicação** | REST API + CORS aberto (origem `*`) |
| **Build Frontend** | Vite → pasta `backend/static/` (servido pelo FastAPI) |
| **Deploy** | Railway (`nvs-production` branch) |
| **ERP** | Tiny ERP v2 API (`api.tiny.com.br/api2/`) via httpx async |
| **IA** | Groq API + Llama 3.3 70B (`llama-3.3-70b-versatile`) |
| **Impressão** | TCP/IP direto para impressoras Zebra (porta 9100) |

### Arquitetura geral

```
Browser (React)
    │
    ▼
FastAPI (Railway)
    ├── /api/* ──────────────── Routers (sessions, tiny, ai, etc.)
    ├── /api/v2/ai ─────────── MAS (Agente NVS / Groq)
    └── / (static) ──────────── Build Vite do React
         │
         ▼
    SQLite DB ◄──── Tiny ERP API (sync) ◄──── Webhook Tiny
                         │
                         ▼
                   ZebraAgent (4 PCs) ──TCP──► Zebra Printer
```

### Estrutura de Pastas

```
warehouse-picker v2/
├── backend/
│   ├── main.py                  # Aplicação FastAPI principal
│   ├── models.py                # 20+ modelos SQLAlchemy
│   ├── database.py              # Engine + sessão SQLite
│   ├── routers/
│   │   ├── sessions.py          # Sessões de picking (bipagem)
│   │   ├── tiny.py              # Integração Tiny ERP + Separação
│   │   ├── ai.py                # Agente NVS (MAS / Groq)
│   │   ├── operators.py         # Operadores e PINs
│   │   ├── labels.py            # Geração de etiquetas ZPL
│   │   ├── printers.py          # Gerenciamento de impressoras
│   │   ├── print_jobs.py        # Fila de impressão
│   │   ├── barcodes.py          # Base de barcodes/SKUs
│   │   ├── stats.py             # Métricas e KPIs
│   │   └── seed.py              # Seed/reset de dados (dev)
│   ├── services/
│   │   ├── tiny_service.py      # Client HTTP Tiny ERP
│   │   └── sync_engine.py       # Motor de sincronização em background
│   ├── mas_core/
│   │   ├── agents.py            # Definição dos agentes (MAS)
│   │   ├── agent_protocol.py    # Protocolo de comunicação entre agentes
│   │   └── ai_service.py        # Client Groq/OpenAI-compatible
│   └── static/                  # Build do React (gerado pelo Vite)
├── frontend/
│   ├── src/
│   │   ├── pages/               # 14 páginas React
│   │   ├── components/          # Componentes reutilizáveis
│   │   ├── api/client.js        # Client HTTP para a API
│   │   └── lib/utils.js         # Utilitários (cn, etc.)
│   └── tailwind.config.js       # Breakpoints personalizados
├── print-agent/                 # ZebraAgent (TCP → impressora)
├── PLANO_DEPLOY_V2.md          # Plano de migração v1→v2
├── publicar_producao.bat        # Script de deploy Railway
└── warehouse_v3_local.db        # Banco de dados SQLite
```

---

## 3. BANCO DE DADOS

O sistema usa **SQLite** com 20+ tabelas organizadas em domínios:

### Domínio: Picking (operação principal)

| Tabela | Descrição |
|---|---|
| `operators` | Operadores de armazém com nome e PIN. Padrão: Master, Julio, Cris, Rafael, Luidi, Weligton, Cristofer, Renan |
| `batches` | Lotes de picking por data de carregamento. Atributos: `full_date`, `seq`, `name`, `status` (active/archived), `marketplace` (ml/shopee) |
| `sessions` | Sessão de trabalho de um operador em um lote. Status: `open → in_progress → completed` |
| `picking_items` | Itens individuais dentro de uma sessão. Status: `pending → in_progress → complete / partial / out_of_stock` |
| `scan_events` | Auditoria de cada bipagem. Tipos: `scan`, `undo`, `shortage`, `out_of_stock`, `substitution`, `reopen` |
| `shortages` | Relatório de faltas por SKU. Categorias: `full` (lote Full) / `organico` (pedido orgânico) |

### Domínio: Impressão

| Tabela | Descrição |
|---|---|
| `labels` | Etiquetas ZPL geradas por sessão/SKU |
| `printers` | Cadastro de impressoras Zebra com IP e porta |
| `print_jobs` | Fila de impressão. Status: `PENDING → PRINTING → PRINTED / ERROR` |
| `barcodes` | Base de dados de códigos de barras mapeados para SKUs |

### Domínio: Tiny ERP / Olist

| Tabela | Descrição |
|---|---|
| `tiny_orders_sync` | Espelho local de pedidos do Tiny (id, numero, ecommerce, marcadores, raw_data) |
| `tiny_order_items` | Itens dos pedidos sincronizados (SKU, quantidade, valor unitário) |
| `orders_operational` | Camada canônica de pedidos para consultas rápidas (status normalizado, canal, datas) |
| `sync_runs` | Auditoria de execuções de sincronização (carga inicial, incremental, reconciliação) |
| `tiny_picking_lists` | Listas de separação geradas a partir de separações do Tiny |
| `tiny_picking_list_items` | Itens consolidados da lista de separação (agrupados por SKU) |
| `tiny_separation_item_cache` | Cache de itens de separação do Tiny (TTL 6h, evita chamadas desnecessárias à API) |
| `tiny_separation_statuses` | Espelho local do status de separações do Tiny (Tiny é somente-leitura) |

### Domínio: IA / MAS

| Tabela | Descrição |
|---|---|
| `agent_memory` | Histórico de conversas por sessão e por agente (role, type, content, tool_call_id) |
| `agent_runs` | Trilhas de execução do ecossistema de agentes para observabilidade e auditoria |

---

## 4. API REST

Base URL: `https://<app>.railway.app`

### Endpoints principais

#### Operadores
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/operators` | Lista todos os operadores |
| POST | `/api/operators` | Cria novo operador |
| POST | `/api/operators/login` | Login por nome + PIN |

#### Sessões de Picking
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/sessions` | Lista sessões (com filtros: status, marketplace, batch_id) |
| POST | `/api/sessions` | Cria nova sessão |
| GET | `/api/sessions/{id}` | Detalhes de sessão + itens |
| POST | `/api/sessions/{id}/pick` | Registra uma bipagem (scan/undo/shortage) |
| POST | `/api/sessions/{id}/complete` | Conclui a sessão |

#### Tiny ERP / Separação
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/tiny/pedidos` | Lista pedidos com cache (3 min) e enriquecimento do espelho local |
| GET | `/api/tiny/separacoes` | Lista separações pendentes do Tiny (últimos 7 dias, situações 1/4/2) |
| POST | `/api/tiny/picking-lists` | Cria lista de separação a partir de separações selecionadas |
| GET | `/api/tiny/picking-lists` | Lista todas as listas de separação |
| GET | `/api/tiny/picking-lists/{id}` | Detalhes de uma lista com itens |
| POST | `/api/tiny/picking-lists/{id}/pick` | Registra picking de um item da lista (com sync Olist em background) |
| POST | `/api/tiny/webhook` | Recebe webhooks do Tiny (sincronização em background) |
| POST | `/api/tiny/sync/vacuum` | Dispara sincronização completa de pedidos (últimos 60 dias) |
| GET | `/api/tiny/sync/status` | Status da sincronização em andamento |

#### Impressão / Etiquetas
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/printers` | Lista impressoras cadastradas |
| POST | `/api/printers` | Cadastra impressora Zebra |
| GET | `/api/labels/{session_id}` | Busca etiquetas de uma sessão |
| POST | `/api/labels/generate` | Gera etiquetas ZPL para uma sessão/SKU |
| GET | `/api/print-jobs` | Fila de impressão |
| POST | `/api/print-jobs/{id}/print` | Envia job para a impressora |

#### Métricas / Stats
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/stats/overview` | KPIs gerais (sessões, itens, faltas, taxa de conclusão) |
| GET | `/api/stats/shortages` | Relatório de faltas agrupado por SKU |

#### IA (Agente NVS)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v2/ai/chat` | Chat com o agente NVS (MAS multi-agente) |

#### Administração
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/health` | Health check com contagem de registros no DB |
| GET | `/api/admin/download-db?secret=` | Download do banco SQLite de produção |
| GET | `/api/admin/logs?n=200` | Últimas N linhas do log central |
| POST | `/api/admin/frontend-log` | Recebe erros do frontend e grava no log central |
| GET | `/api/admin/seed-now` | Força cópia do banco de repo para volume Railway |

---

## 5. PÁGINAS DO FRONTEND

| Página | Rota | Acesso | Descrição |
|---|---|---|---|
| `Login` | `/` | Todos | Tela de login por nome + PIN de 4 dígitos |
| `SessionSelect` | `/sessions` | Operadores | Visão do operador: sessões ativas, listas disponíveis e histórico (via `?view=`) |
| `Picking` | `/picking/:sessionId` | Operadores | Tela de bipagem item a item com leitor de barcode |
| `PickingListDetail` | `/separacao/listas/:id` | Todos | Detalhe de lista de separação Tiny com modal de picking |
| `PickingListsHistory` | `/separacao/listas` | Todos | Histórico de todas as listas de separação geradas |
| `SeparacaoOlist` | `/separacao` | Todos | Central de separações do Tiny ERP com tabs (aguardando/em separação/concluído) |
| `Supervisor` | `/supervisor` | Master | Visão geral de todos os lotes ML e Shopee com métricas de progresso |
| `BatchDetail` | `/supervisor/ml/lists` ou `/supervisor/shopee/lists` | Master | Detalhe de lotes e sessões por marketplace |
| `OlistOrders` | `/olist-orders` | Master | Espelho de pedidos sincronizados do Tiny ERP |
| `GemmaDashboard` | `/supervisor/ml/overview` ou `/supervisor/shopee/overview` | Master | Dashboard com agente NVS integrado e métricas de vendas |
| `ShortageReport` | `/shortage-report` | Todos | Relatório consolidado de faltas por SKU |
| `MasterData` | `/master-data` | Master | Base de dados de SKUs e barcodes (cadastro e edição) |
| `OperatorsManagement` | `/operators` | Master | Gerenciamento de operadores (criar, editar, PIN) |
| `SessionItems` | `/sessions/:id/items` | Todos | Detalhes dos itens de uma sessão específica |

### Permissões de menu

**Usuário Master** vê: Supervisão Full, Separação, Faltas, ERP Olist, Base, Operadores

**Demais operadores** veem: Sessões, Listas Disponíveis, Listas Concluídas, Faltantes, Separação

---

## 6. FLUXO OPERACIONAL

### 6.1 Fluxo Full (Mercado Livre / Shopee)

```
Supervisor cria lote (Batch)
    │
    ▼
Supervisor importa lista de itens (CSV ou manual)
    │
    ▼
Sessões são distribuídas para operadores
    │
    ▼
Operador faz login → seleciona sessão
    │
    ▼
Tela de Picking: operador vê item + qty → bipa barcode
    ├── scan      → qty_picked++ → se qty_picked == qty_required → status = complete
    ├── shortage  → registra falta (qty_shortage) → status = partial ou out_of_stock
    └── undo      → reverte último scan
    │
    ▼
Ao completar todos os itens → sessão vai para "completed"
    │
    ▼
Etiquetas ZPL geradas automaticamente → enviadas à impressora Zebra via TCP
    │
    ▼
Supervisor acompanha progresso em tempo real no Supervisor Dashboard
```

### 6.2 Fluxo Separação (Tiny ERP / Olist)

```
Tiny ERP cria documentos de separação (situações 1, 4, 2)
    │
    ▼
SeparacaoOlist busca separações dos últimos 7 dias
    │
    ▼
Supervisor/Operador seleciona separações → cria Lista de Separação
    │
    ▼
Itens consolidados por SKU (soma de quantidades de múltiplas separações)
    │
    ▼
Operador acessa lista → PickingListDetail → bipa cada item
    ├── pick      → qty_picked++
    └── shortage  → registra falta
    │
    ▼
Quando todos os itens são concluídos → lista muda para "concluida"
    │
    ▼
[ENABLE_OLIST_SYNC=true em PRD]
Background task chama Tiny API → atualiza situação da separação para "separado"
    │
    ▼
[ENABLE_OLIST_SYNC=false local]
DRY-RUN: apenas loga sem tocar a API do Tiny
```

### 6.3 Fluxo de Impressão (ZebraAgent)

```
Item bipado como "complete" → backend gera ZPL → PrintJob criado (PENDING)
    │
    ▼
ZebraAgent (4 PCs locais) → polling de /api/print-jobs
    │
    ▼
PrintJob enviado via TCP socket → porta 9100 → Impressora Zebra
    │
    ▼
Status atualizado → PRINTED (ou ERROR se falha TCP)
```

---

## 7. SISTEMA DE INTELIGÊNCIA ARTIFICIAL (NVS Agent)

### Arquitetura MAS (Multi-Agent System)

O NVS Agent usa um padrão **Hub-and-Spoke** com orquestrador + especialistas:

```
Usuário → ORCHESTRATOR (classifica intenção)
              │
              ├──► DATA_SCIENTIST      (métricas de vendas, análises estatísticas)
              ├──► GROWTH_STRATEGIST   (oportunidades de crescimento e expansão)
              ├──► COPYWRITER          (textos, anúncios, descrições de produtos)
              ├──► ART_DIRECTOR        (identidade visual, apresentações)
              └──► BI_ANALYST          (dashboards, KPIs, relatórios gerenciais)
```

### Configuração

| Parâmetro | Valor |
|---|---|
| **Provider** | Groq API |
| **Modelo** | `llama-3.3-70b-versatile` |
| **Base URL** | `https://api.groq.com/openai/v1` |
| **Memória** | Persistida em SQLite (`agent_memory`) por `session_id` + `agent_role` |
| **Observabilidade** | Trilhas de execução em `agent_runs` (status, tool calls, confiança, erros) |

### Ferramentas disponíveis para o Agente

| Tool | Descrição |
|---|---|
| `show_orders_grid_ui` | Renderiza grade operacional de pedidos na UI |
| `get_inventory_data` | Consulta estoque, giro e risco de ruptura por SKU |
| `analyze_marketplace_performance` | Analisa performance ML vs Shopee vs orgânico |
| `get_sales_trend` | Tendência de vendas com análise comparativa |
| `get_shortage_report` | Relatório de faltas para reposição |
| `get_operational_summary` | Resumo operacional do dia/semana |

---

## 8. INTEGRAÇÃO TINY ERP (OLIST)

### TinyService — Client HTTP

O `TinyService` (`backend/services/tiny_service.py`) encapsula todas as chamadas à API Tiny v2:

| Método | Endpoint Tiny | Descrição |
|---|---|---|
| `search_orders` | `pedidos.pesquisa.php` | Busca pedidos com paginação automática (até 100 páginas) |
| `search_separations` | `separacao.pesquisa.php` | Busca separações por situação (1, 4, 2) |
| `get_order_details` | `pedido.obter.php` | Detalhes completos de um pedido |
| `get_separation_details` | `separacao.obter.php` | Detalhes completos de uma separação |
| `get_multi_separation_items` | `separacao.obter.php` (paralelo, lotes de 12) | Consolida itens de múltiplas separações por SKU |
| `update_separation_status` | `separacao.alterar.situacao.php` | Atualiza situação de separação (**PRD apenas**) |
| `get_faturados_numeros` | `pedidos.pesquisa.php` | Busca números de pedidos faturados no período |

### Proteções anti-rate-limit

- Delay de **0.4s** entre páginas na busca de pedidos
- Delay de **0.2s** entre lotes na consolidação de separações
- **Cache em memória** de 3 minutos na listagem de pedidos (`_PEDIDOS_CACHE`)
- **Cache em SQLite** de itens de separação (`tiny_separation_item_cache`) com TTL de 6h

### Webhook

O Tiny pode enviar webhooks ao endpoint `POST /api/tiny/webhook`. Ao receber um evento de pedido, o sistema agenda uma sincronização em background sem bloquear a resposta ao Tiny (necessário retornar 200 imediatamente para não desativar o webhook).

### Feature Gate: Sync de Status para o Olist

Controlado pela variável de ambiente `ENABLE_OLIST_SYNC`:

```
ENABLE_OLIST_SYNC=false   → DRY-RUN: apenas loga "[OLIST_SYNC=OFF]" sem chamar a API
ENABLE_OLIST_SYNC=true    → PRD: chama a API Tiny e atualiza a situação da separação
```

**Ativar em PRD:** setar `ENABLE_OLIST_SYNC=true` no painel Railway.
**⚠️ Verificar antes:** confirmar o endpoint `separacao.alterar.situacao.php` e o valor `separado` para o parâmetro `situacao` na documentação Tiny v2.

---

## 9. IMPRESSÃO ZEBRA (ZebraAgent)

### Arquitetura

O **ZebraAgent** é um agente local instalado em **4 máquinas** no armazém. Ele:
1. Faz polling periódico no endpoint `/api/print-jobs` buscando jobs `PENDING`
2. Abre uma conexão TCP/IP para a impressora Zebra na porta **9100**
3. Envia o conteúdo ZPL
4. Atualiza o status do job para `PRINTED` ou `ERROR`

### Configuração por máquina

```env
BACKEND_URL = https://<app>.railway.app
```

### Formato de etiqueta

As etiquetas são geradas em **ZPL (Zebra Programming Language)** diretamente pelo backend. O conteúdo é armazenado na tabela `labels` e também na coluna `zpl_content` do `print_jobs`.

---

## 10. LAYOUT E UX

### Breakpoints

O sistema usa breakpoints customizados além dos padrões do Tailwind:

```js
screens: {
  'xs': '400px',       // Telefones pequenos
  'sm': '640px',       // Tailwind padrão
  'md': '768px',       // Tailwind padrão (tablets portrait)
  'tablet': '900px',   // Tablets intermediários
  'lg': '1024px',      // Desktop (sidebar aparece a partir daqui)
  ...
}
```

### Estratégia de layout

- **Mobile-first** — todos os componentes são desenhados para mobile e expandidos para desktop
- **Sidebar** aparece em `lg:` (1024px+) — tablets ficam com layout mobile (full-width + bottom nav)
- **Sub-menus dinâmicos** — quando em rotas com sub-navegação (`/separacao/*` ou `/supervisor/ml/*` ou `/supervisor/shopee/*`), uma barra horizontal sticky aparece entre o header e o conteúdo no mobile
- **Bottom navigation** — barra fixa no rodapé mobile com os itens de menu principais
- **Touch targets** — mínimo de `44px` de altura em elementos interativos (WCAG 2.1)
- **Modais** — usam `max-w-md w-full` + `max-h-[90vh] overflow-y-auto` para funcionamento correto em todas as telas

### Tema visual

- **Paleta**: `slate-900` (fundo sidebar), `cyan-500` (acento ativo), `blue-500` (gradientes)
- **Tipografia**: `font-sans`, hierarquia clara de tamanhos
- **Componentes**: shadcn/ui adaptados + Lucide React para ícones

---

## 11. OPERADORES E AUTENTICAÇÃO

O sistema usa **autenticação por sessão no navegador** (`sessionStorage`):

1. Operador seleciona seu nome na lista
2. Digita PIN de 4 dígitos
3. Backend valida e retorna os dados do operador
4. Frontend armazena em `sessionStorage.operator` (limpo ao fechar a aba)

### Usuário Master

O operador **Master** tem acesso completo:
- Supervisão de todos os lotes e sessões
- Gerenciamento de operadores
- Acesso à base de dados (SKUs/barcodes)
- Tela de pedidos ERP Olist
- Vacuum/sync da base de dados Tiny

Todos os demais operadores acessam apenas: Sessões, Listas, Faltantes e Separação.

---

## 12. DEPLOY

### Infraestrutura

| Item | Configuração |
|---|---|
| **Plataforma** | Railway |
| **Branch de deploy** | `nvs-production` |
| **Script de deploy** | `publicar_producao.bat` |
| **Container** | Docker (Nixpacks) — `nixpacks.toml` + `Dockerfile` |
| **Volume persistente** | `/data/warehouse_v3_local.db` (banco SQLite em produção) |
| **Static files** | `backend/static/` (build React servido pelo FastAPI) |

### Variáveis de ambiente (Railway)

```env
DATABASE_URL                 = /data/warehouse_v3_local.db
TINY_API_TOKEN               = <token da API Tiny>
GROQ_API_KEY                 = <chave Groq>
DOWNLOAD_SECRET              = <senha para download do DB>
ENABLE_LOCAL_SYNC_SCHEDULER  = true
ENABLE_OLIST_SYNC            = false   # → true ao ativar sync de status PRD
TINY_SEPARATION_DONE_SITUACAO = separado
```

### Plano de migração v1 → v2

O sistema está em versão 2.0, que **não está em produção ainda** (aguarda validação). A versão 1.0 continua rodando. O plano de deploy em 5 etapas:

| Etapa | Ação | Risco |
|---|---|---|
| 1 | Criar novo projeto Railway para v2 | Zero |
| 2 | Baixar banco v1 e testar localmente na v2 | Zero |
| 3 | Deploy v2 em paralelo (v1 continua ativo) | Baixo |
| 4 | Migrar ZebraAgents um por um (2-5 min/máquina) | Médio |
| 5 | Pausar v1 no Railway (manter 7 dias de standby) | Zero |

**Rollback em menos de 5 minutos**: reativar v1 no Railway + reverter `BACKEND_URL` nos ZebraAgents.

---

## 13. LOGGING E DIAGNÓSTICO

### Log central

- Todas as requisições HTTP são logadas pelo middleware `request_logger`
- Erros 4xx/5xx geram entrada de warning/error no log
- Frontend pode enviar erros via `POST /api/admin/frontend-log`
- Logs disponíveis via `GET /api/admin/logs?n=200`

### Observabilidade de IA

- Cada interação com o agente gera um registro em `agent_runs` com:
  - `request_id`, `session_id`, `user_prompt`
  - `specialist_role` acionado
  - `tool_name` + `tool_args_json` + `tool_result_json`
  - `confidence` (computed)
  - `status` (started / completed / error)
  - `created_at` / `completed_at`

### Diagnóstico de sync Tiny

- Cada execução de sync registrada em `sync_runs` com:
  - `sync_type` (full / incremental / targeted / reconciliation)
  - `orders_seen`, `orders_inserted`, `orders_updated`, `orders_failed`
  - `window_start` / `window_end` da janela de dados
  - `started_at` / `finished_at`

---

## 14. ESTADO ATUAL E PRÓXIMOS PASSOS

### O que está feito (v2.2)

- [x] Picking completo de lotes Full (ML + Shopee) com barcode
- [x] Supervisão em tempo real de sessões e lotes
- [x] Integração Tiny ERP: pedidos, separações, webhook
- [x] Listas de separação geradas a partir de separações Tiny
- [x] Cache inteligente de itens de separação (TTL 6h)
- [x] Picking de itens de separação com registro de faltas
- [x] Feature gate `ENABLE_OLIST_SYNC` para sync de status (DRY-RUN local, ativo em PRD)
- [x] Agente NVS com MAS (Groq + Llama 3.3 70B) + memória persistida
- [x] Geração e impressão de etiquetas ZPL via Zebra
- [x] ZebraAgent em 4 máquinas locais
- [x] Download de banco de produção protegido por segredo
- [x] Relatório de faltas (Full + Orgânico) com filtros
- [x] Base de dados de SKUs/barcodes com CRUD
- [x] Gerenciamento de operadores com PIN
- [x] Layout responsivo mobile-first com sidebar `lg:`, sub-menus móveis, bottom nav
- [x] Separação acessível a todos os operadores (não apenas Master)
- [x] Logging de erros do frontend no log central

### Pendente antes do go-live v2

- [ ] Verificar endpoint e código `situacao` correto na API Tiny v2 para `update_separation_status`
- [ ] Executar plano de deploy 5 etapas (PLANO_DEPLOY_V2.md)
- [ ] Atualizar URL nos 4 ZebraAgents após deploy
- [ ] Ativar `ENABLE_OLIST_SYNC=true` no Railway após validação do endpoint Tiny

---

*Documento gerado em 2026-04-19 | NVS-WMS v2.2 | Novaes Moto Peças*

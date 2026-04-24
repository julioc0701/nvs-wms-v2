# CODEBASE.md — Warehouse Picker (NVS·WMS)

> Documento de referência rápida do projeto. Leia este arquivo ANTES de abrir qualquer outro.
> Última atualização: 2026-04-23

---

## Stack e Arquitetura

| Camada | Tecnologia | Observação |
|---|---|---|
| **Backend** | Python + FastAPI + Uvicorn | Roda na porta 8001 |
| **Banco de dados** | SQLite (SQLAlchemy ORM) | Arquivo `warehouse_v3_local.db` |
| **Frontend** | React 18 + Vite | SPA, comunica via `/api` |
| **Deploy** | Railway (Docker) | Branch `nvs-production` |
| **Impressão** | ZebraAgent-WP.exe (local) | Polling no backend a cada 2s |
| **Integração ERP** | Tiny ERP (Olist) via API v2 | Token: `TINY_API_TOKEN` |

---

## Estrutura de Arquivos — Mapa Rápido

```
warehouse-picker v2/
├── backend/
│   ├── main.py                    ← FastAPI app, routers, startup, scheduler
│   ├── models.py                  ← Todos os modelos SQLAlchemy (tabelas)
│   ├── database.py                ← Engine, sessões, init_db(), migrações inline
│   ├── services/
│   │   ├── picking.py             ← Lógica central de bipagem (Full/Orgânico)
│   │   ├── tiny_service.py        ← HTTP client assíncrono para a API Tiny
│   │   └── sync_engine.py         ← Scheduler de sync + job ERP auto-send (5 min)
│   ├── routers/
│   │   ├── sessions.py            ← Criar/listar sessões, scan, shortage, oos
│   │   ├── barcodes.py            ← CRUD SKU/EAN, import Excel, resolve barcode
│   │   ├── print_jobs.py          ← Fila de impressão (criar, pendentes, atualizar)
│   │   ├── operators.py           ← Login, PIN, CRUD operadores
│   │   ├── labels.py              ← ZPL manual, mark-printed
│   │   ├── stats.py               ← Ranking de operadores
│   │   ├── printers.py            ← CRUD de impressoras cadastradas
│   │   └── tiny.py                ← INTEGRAÇÃO TINY (Separação, Picking, ERP Send)
│   └── warehouse_v3_local.db      ← Banco LOCAL (seed para produção)
│
├── frontend/
│   └── src/
│       ├── App.jsx                ← Roteamento React
│       ├── api/client.js          ← TODAS as chamadas de API centralizadas aqui
│       └── pages/
│           ├── Picking.jsx              ← Tela principal WMS (Full/Orgânico)
│           ├── PickingListDetail.jsx    ← Separação Tiny (picking de lista)
│           ├── SeparacaoOlist.jsx       ← Gestão de separações Tiny (5 abas)
│           ├── SeparacaoListas.jsx      ← Listas de picking geradas
│           ├── SessionItems.jsx         ← Lista de itens da sessão
│           ├── Login.jsx                ← Login do operador (PIN)
│           ├── Supervisor.jsx           ← Painel supervisor
│           ├── MasterData.jsx           ← CRUD de produtos e barcodes
│           ├── ShortageReport.jsx       ← Relatório de faltas
│           └── OperatorsManagement.jsx  ← Gestão de operadores
│
├── print-agent/
│   ├── agent.py                   ← Código fonte do agente de impressão
│   ├── ZebraAgent-WP.exe          ← Executável compilado (para operadores)
│   └── iniciar_producao.bat       ← Script para iniciar o agente em produção
│
├── publicar_producao.bat          ← Deploy manual para Railway (branch nvs-production)
├── Dockerfile                     ← Build da imagem Docker
└── railway.toml                   ← Configuração do Railway
```

---

## Modelos do Banco de Dados

### WMS Core
| Tabela | Campos principais | Descrição |
|---|---|---|
| `operators` | id, name, badge, pin_code | Operadores da expedição |
| `sessions` | id, session_code, operator_id, status, batch_id, marketplace | Ordens de separação |
| `picking_items` | id, session_id, sku, qty_required, qty_picked, shortage_qty, status, labels_printed, ml_code | Itens de cada sessão |
| `barcodes` | id, barcode, sku, description, is_primary | Master Data EAN→SKU |
| `batches` | id, full_date, seq, name, status, marketplace | Agrupamento de sessões por dia/batch |
| `print_jobs` | id, session_id, sku, zpl_content, status | Fila de impressão |
| `shortages` | id, sku, description, quantity, category, list_id, operator_id, notes | Relatório de faltas |

### Tiny ERP — Separação
| Tabela | Campos principais | Descrição |
|---|---|---|
| `tiny_picking_lists` | id, name, status, created_at | Listas de separação consolidadas |
| `tiny_picking_list_items` | id, list_id, sku, quantity, qty_picked, qty_shortage, is_shortage, notes, location, source_separation_ids | Itens consolidados |
| `tiny_separation_statuses` | id, separation_id (unique), status, list_id, created_at | Espelho local do status dos docs. Tiny é read-only. Valores: `em_separacao`, `concluida`, `enviada_erp`, `erro_envio_erp`, `aguardando` |
| `tiny_separation_headers` | id, separation_id (unique), numero, destinatario, numero_ec, data_emissao, prazo_maximo, id_forma_envio, forma_envio_descricao, numero_pedido, updated_at | Cache de display dos docs do Tiny |
| `tiny_separation_item_cache` | id, separation_id, sku, description, quantity, location, cached_at | Cache de itens por separação (TTL 6h) |
| `tiny_erp_send_logs` | id, separation_id, triggered_by, status, response_json, error_message, sent_at | Auditoria de envios ERP. `triggered_by`: `manual`/`auto`. `status`: `success`/`error` |

### Tiny ERP — Sync de Pedidos
| Tabela | Campos principais | Descrição |
|---|---|---|
| `tiny_order_syncs` | id, numero, status, ecommerce, raw_data, last_synced_at | Espelho local de pedidos Tiny |
| `order_operational` | id, order_id, numero, current_status, status_bucket | Camada canônica de pedidos |
| `sync_runs` | id, sync_type, status, started_at, finished_at | Log de execuções do scheduler |

---

## Rotas da API — Referência Rápida

### Integração Tiny `/api/tiny`

#### Separações (fluxo principal)
| Método | Rota | O que faz |
|---|---|---|
| GET | `/separacoes` | Busca docs `situacao=1` (aguardando) do Tiny com paginação completa |
| GET | `/tracked-separacoes` | Docs rastreados no DB local (em_separacao + concluida + enviada_erp + erro_envio_erp) sem filtro de data |
| GET | `/separation-statuses` | Mapa `separation_id → {status, list_id}` |
| POST | `/separation-statuses/revert` | Devolve docs para aguardando (apaga registro local) |
| POST | `/separation-statuses/delete` | Remove rastreamento local do doc |
| **POST** | **`/separation-statuses/enviar-erp`** | **Envia docs para Tiny via `situacao=2`. Grava log. Manual ou automático.** |
| GET | `/erp-send-logs/{sep_id}` | Histórico de envios ERP de um documento |

#### Picking Lists
| Método | Rota | O que faz |
|---|---|---|
| POST | `/picking-lists` | Cria lista consolidada a partir de separation_ids |
| GET | `/picking-lists` | Lista todas as listas |
| GET | `/picking-lists/{id}` | Detalhes + itens + progresso |
| DELETE | `/picking-lists/{id}` | Remove lista e reverte docs |
| POST | `/picking-items/{id}/pick` | Bipa item (modes: unit/box/set) |
| POST | `/picking-items/{id}/unpick` | Desfaz pick |
| POST | `/picking-items/{id}/clear-shortage` | Remove falta do item |

#### Separação — Detalhes e Cache
| Método | Rota | O que faz |
|---|---|---|
| GET | `/separacao/{sep_id}` | Detalhes completos + progresso de picking |
| POST | `/separation-cache/warm` | Pré-aquece cache de itens em background |
| GET | `/product-image/{sku}` | URL da imagem do produto (Tiny) |

### Sessões `/api/sessions`
| Método | Rota | O que faz |
|---|---|---|
| GET | `/` | Lista todas as sessões |
| POST | `/upload` | Upload de Excel para criar sessão |
| POST | `/{id}/scan` | Bipa um código de barras |
| POST | `/{id}/shortage` | Registra falta de quantidade |
| POST | `/{id}/out-of-stock` | Marca como sem estoque |

### Códigos de Barras `/api/barcodes`
| Método | Rota | O que faz |
|---|---|---|
| POST | `/import-excel` | Importa mapeamento EAN→SKU do Excel |
| GET | `/resolve?barcode=` | Resolve EAN para SKU |
| GET | `/` | Lista todos os produtos |
| POST | `/product` | Cria produto manual |

---

## Fluxo de Separação Tiny — 5 Abas

```
[aguardando separação]  ← busca manual via filtro de data no Tiny (situacao=1)
        ↓  (gerar lista)
[em separação]          ← local DB. Docs incluídos em picking list.
        ↓  (picking completo)
[separadas]             ← local DB. Todos os itens coletados/shortage.
        ↓  (enviar para ERP — manual ou automático a cada 5 min)
[enviadas ERP]          ← local DB. Tiny confirmou (status=OK). Badge ✅/❌.
        ↓  (Tiny processa)
[embaladas/checkout]    ← Tiny API. situacao=3.
```

### Princípio fundamental
O Tiny é **read-only** da nossa perspectiva de status. Todo estado é gerenciado localmente em `tiny_separation_statuses`. A única escrita que fazemos no Tiny é o envio via `separacao.alterar.situacao.php` (situacao=2) quando o doc é enviado para "Enviadas ERP".

---

## Scheduler Automático (sync_engine.py)

Ativado via env var `ENABLE_LOCAL_SYNC_SCHEDULER=true`.

| Job | Intervalo | O que faz |
|---|---|---|
| `scheduler_loop` | `SYNC_INCREMENTAL_INTERVAL_MINUTES` (default: 10 min) | Sync incremental de pedidos Tiny |
| `erp_sync_loop` | `ERP_SYNC_INTERVAL_SECONDS` (default: 300s = 5 min) | Envia todos os docs `status=concluida` para o Tiny automaticamente |

---

## Mobile UX — Picking (PickingListDetail.jsx)

Comportamento especial para `window.innerWidth < 768`:
- **Redirecionamento**: operadores não-Master no celular são redirecionados para `/separacao/listas`
- **Auto-seleção**: ao abrir uma lista, o primeiro item pendente (maior qty) é selecionado automaticamente
- **Auto-avanço**: ao concluir/shortage um item, avança automaticamente para o próximo pendente (delay 800ms)
- **Botão "Próximo →"**: navega para o próximo item pendente (disponível em mobile e desktop)
- **Progress badge**: mostra `X / Y` itens concluídos no modal
- **Cards mobile**: lista de itens exibida como cards em vez de tabela (`md:hidden`)
- **Copy→Bipe**: clicar no ícone de cópia ao lado do SKU injeta o código no campo de bipe e processa automaticamente

---

## Variáveis de Ambiente (Railway)

| Variável | Valor em PRD | Descrição |
|---|---|---|
| `DATABASE_URL` | `sqlite:////data/warehouse_v3_local.db` | Caminho do banco no volume Railway |
| `FORCE_SEED` | `false` | Se `true`, sobrescreve banco com seed do repo |
| `TINY_API_TOKEN` | `<token>` | Token da API Tiny ERP |
| `ENABLE_LOCAL_SYNC_SCHEDULER` | `true` | Ativa scheduler de sync de pedidos + ERP auto-send |
| `ENABLE_OLIST_SYNC` | `true` | Push automático de status ao Tiny ao picar item |
| `ENABLE_TINY_WEBHOOK` | `true` | Recebe eventos do Tiny (inserção/alteração de pedidos) |
| `ERP_SYNC_INTERVAL_SECONDS` | `300` | Intervalo do job ERP auto-send (segundos, default: 300) |
| `GROQ_API_KEY` | `<chave>` | Chave da API Groq (NVS AI) |

---

## Fluxo de Git / Deploy

```
Branch 'main'           → Desenvolvimento local (não afeta Railway)
Branch 'nvs-production' → Produção Railway (deploy automático ao receber push)

Para publicar:  double-click em publicar_producao.bat → pressionar S
```

---

## Regras Importantes (NÃO MUDAR sem verificar)

1. **`barcodes` NÃO tem UNIQUE no campo `barcode`** — um EAN pode estar em múltiplos SKUs.
2. **Tiny é read-only** — nunca escrever status de volta no Tiny, exceto via `separacao.alterar.situacao.php` (situacao=2) no fluxo ERP Send.
3. **`TinyService._post`** retorna o conteúdo do `retorno` já desembalado. Não fazer `resp.get("retorno", {})` — usar `resp.get("retorno", resp)` para suportar ambos os formatos.
4. **`autoAdvance` no PickingListDetail** lê refs DENTRO do setTimeout(800ms) para evitar stale closures.
5. **Migrações** são inline em `database.py` → `init_db()`. Nunca usar `migrate_db.py` externo em produção.
6. **Deploy automático está DESATIVADO para `main`** — apenas `nvs-production` faz deploy no Railway.

---

## Operadores Padrão

Master, Julio, Cris, Rafael, Luidi, Weligton, Cristofer, Renan
*(criados automaticamente no startup se não existirem — PIN padrão: 1234)*

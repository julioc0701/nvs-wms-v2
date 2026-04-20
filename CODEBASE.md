# CODEBASE.md — Warehouse Picker (NVS)

> Documento de referência rápida do projeto. Leia este arquivo ANTES de abrir qualquer outro.
> Última atualização: 2026-03-17

---

## 🏗️ Stack e Arquitetura

| Camada | Tecnologia | Observação |
|---|---|---|
| **Backend** | Python + FastAPI + Uvicorn | Roda na porta 8000 |
| **Banco de dados** | SQLite (SQLAlchemy ORM) | Arquivo `warehouse_v2.db` |
| **Frontend** | React (Vite) | SPA, comunica via `/api` |
| **Deploy** | Railway (Docker) | Branch `nvs-production` |
| **Impressão** | ZebraAgent-WP.exe (local) | Polling no backend a cada 2s |

---

## 📂 Estrutura de Arquivos — Mapa Rápido

```
warehouse-picker/
├── backend/
│   ├── main.py                  ← FastAPI app, routers, startup
│   ├── models.py                ← Todos os modelos SQLAlchemy (tabelas)
│   ├── database.py              ← Engine, sessões, init_db(), migrações
│   ├── services/
│   │   └── picking.py           ← LÓGICA CENTRAL de bipagem e separação
│   ├── routers/
│   │   ├── sessions.py          ← Criar/listar sessões, scan, shortage, oos
│   │   ├── barcodes.py          ← CRUD SKU/EAN, import Excel, resolve barcode
│   │   ├── print_jobs.py        ← Fila de impressão (criar, pendentes, atualizar)
│   │   ├── operators.py         ← Login, PIN, CRUD operadores
│   │   ├── labels.py            ← ZPL manual, mark-printed
│   │   ├── seed.py              ← Endpoints de seed/migração de dados
│   │   ├── stats.py             ← Ranking de operadores
│   │   ├── printers.py          ← CRUD de impressoras cadastradas
│   │   └── tiny.py              ← INTEGRAÇÃO TINY (Separação, Sincronia, Picking)
│   └── warehouse_v2.db          ← Banco LOCAL (seed para produção)
│
├── frontend/
│   └── src/
│       ├── App.jsx              ← Roteamento React
│       ├── api/client.js        ← TODAS as chamadas de API centralizadas aqui
│       └── pages/
│           ├── Picking.jsx      ← ⭐ Tela principal (WMS Full/Orgânico)
│           ├── PickingListDetail.jsx ← ⭐ NOVO: Separação Tiny (Lógica WMS)
│           ├── SessionItems.jsx ← Lista de itens da sessão (visão geral)
│           ├── SessionSelect.jsx← Seleção/upload de sessões
│           ├── Login.jsx        ← Login do operador (badge ou PIN)
│           ├── Supervisor.jsx   ← Painel supervisor (upload Excel, gestão)
│           ├── MasterData.jsx   ← CRUD de produtos e codes de barra
│           ├── ShortageReport.jsx← Relatório de faltas
│           └── OperatorsManagement.jsx ← Gestão de operadores
│           └── components/dialogs/
│               ├── ShortageDialog.jsx       ← Dialog de falta manual
│               ├── UnknownBarcodeDialog.jsx ← Código não reconhecido
│               ├── TransferConfirmDialog.jsx← Confirmação de transferência
│               ├── SearchSelectionDialog.jsx← Seleção quando múltiplos SKUs
│               └── WrongSkuDialog.jsx       ← SKU errado na sessão
│
├── print-agent/
│   ├── agent.py                 ← Código fonte do agente de impressão
│   ├── ZebraAgent-WP.exe        ← Executável compilado (para operadores)
│   └── iniciar_producao.bat     ← Script para iniciar o agente em produção
│
├── publicar_producao.bat        ← ⚠️ Deploy manual para Railway (branch nvs-production)
├── Dockerfile                   ← Build da imagem Docker
└── railway.toml                 ← Configuração do Railway
```

---

## 🗄️ Modelos do Banco de Dados

| Tabela | Campos principais | Descrição |
|---|---|---|
| `operators` | id, name, badge, pin_code | Operadores da expedição |
| `sessions` | id, session_code, operator_id, status | Ordens de separação (aberta/em progresso/completa) |
| `picking_items` | id, session_id, sku, qty_required, qty_picked, shortage_qty, status, labels_printed | Itens de cada sessão |
| `tiny_picking_lists` | id, name, status, created_at | Listas de separação do Tiny |
| `tiny_picking_list_items` | id, list_id, sku, qty_picked, qty_shortage, is_shortage | Itens consolidados Tiny |
| `barcodes` | id, barcode, sku, description, is_primary | Master Data EAN→SKU (**sem UNIQUE no barcode** — um EAN pode ter múltiplos SKUs) |
| `print_jobs` | id, session_id, sku, zpl_content, status (PENDING/PRINTING/PRINTED/ERROR) | Fila de impressão para o agente |
| `labels` | id, session_id, sku, label_index, zpl_content, printed | Labels geradas (legado) |
| `scan_events` | id, session_id, picking_item_id, barcode, operator_id, event_type | Auditoria de bipagens |
| `printers` | id, name, ip_address, port | Impressoras cadastradas |

---

## 🔌 Rotas da API — Referência Rápida

### Sessões `/api/sessions`
| Método | Rota | O que faz |
|---|---|---|
| GET | `/` | Lista todas as sessões |
| POST | `/upload` | Upload de Excel para criar sessão |
| POST | `/{id}/scan` | Bipa um código de barras |
| POST | `/{id}/scan-box` | Bipa com confirmação de caixa |
| POST | `/{id}/shortage` | Registra falta de quantidade |
| POST | `/{id}/out-of-stock` | Marca como sem estoque |
| POST | `/{id}/undo` | Desfaz última bipagem |
| POST | `/{id}/force-complete` | Força conclusão manual de item |
| POST | `/{id}/reset-item` | Zera um item da sessão |
| GET | `/find-by-barcode` | Encontra sessão por código de barras |

### Integração Tiny `/api/tiny`
| Método | Rota | O que faz |
|---|---|---|
| GET | `/separacoes` | Lista pedidos/separações do Tiny |
| POST | `/generate-picking` | Consolida pedidos em lista de separação |
| POST | `/picking-items/{id}/pick` | Altera quantidade coletada (Lógica WMS) |
| POST | `/picking-items/{id}/shortage` | Registra falta e observação |

### Códigos de Barras `/api/barcodes`
| Método | Rota | O que faz |
|---|---|---|
| POST | `/import-excel` | Importa mapeamento EAN→SKU do Excel |
| GET | `/resolve?barcode=` | Resolve EAN para SKU(s) |
| GET | `/` | Lista todos os produtos com seus EANs |
| POST | `/product` | Cria produto manual |
| POST | `/{sku}/barcode` | Adiciona EAN a um SKU existente |
| DELETE | `/{sku}/barcode/{barcode}` | Remove EAN de um SKU |

### Fila de Impressão `/api/print-jobs`
| Método | Rota | O que faz |
|---|---|---|
| POST | `/` | Cria job de impressão (chamado pelo frontend em PRD) |
| GET | `/pending` | Retorna jobs pendentes (chamado pelo agente) |
| PATCH | `/{job_id}` | Atualiza status do job (chamado pelo agente) |

---

## 🖨️ Fluxo de Impressão

```
Usuário bipa item → Item completo → autoPrintLabels() no Picking.jsx
    │
    ├─ HTTP (localhost)   → POST direto para ZebraAgent em 127.0.0.1:9100
    │
    └─ HTTPS (produção)  → POST para /api/print-jobs (cria job na fila)
                               ↓
                         ZebraAgent-WP.exe (máquina do operador)
                         faz polling GET /api/print-jobs/pending a cada 2s
                               ↓
                         Imprime ZPL na Zebra ZD220
                         PATCH /api/print-jobs/{id} com status PRINTED
```

---

## 🌳 Fluxo de Git / Deploy

```
Branch 'main'         → Ambiente de desenvolvimento (NÃO afeta Railway)
Branch 'nvs-production' → Produção Railway (deploy automático ao receber push)

Para publicar:  double-click em publicar_producao.bat → pressionar S
```

### Commits recentes relevantes
- `f30063e` — DefectAdjustDialog: input é a quantidade válida, sistema calcula OOS
- `67df25a` — Modal de Ajuste por Defeito para item já concluído
- `7f126be` — Impressão automática em todos os fluxos com await
- `7619403` — Fix: impressão automática pós-bipagem (shortage + oos)
- `e9f2d89` — Botão Reimprimir pede quantidade via dialog
- `12b8474` — Remove UNIQUE constraint da tabela barcodes

---

## ⚙️ Variáveis de Ambiente (Railway)

| Variável | Valor em PRD | Descrição |
|---|---|---|
| `DATABASE_URL` | `sqlite:////data/nvs_prod.db` | Caminho do banco no volume Railway |
| `FORCE_SEED` | `false` | Se `true`, sobrescreve banco com seed do repo |

### Variáveis do Print Agent (máquina do operador)
| Variável | Valor | Descrição |
|---|---|---|
| `ENABLE_POLLING` | `1` | Ativa o polling no backend |
| `BACKEND_URL` | `https://nvs-producao.up.railway.app/api` | URL da API em PRD |
| `POLL_INTERVAL` | `2` | Segundos entre verificações |
| `PRINTER_NAME` | `ZDesigner ZD220-203dpi ZPL` | Nome exato da impressora no Windows |

---

## 🛑 Regras Importantes (NÃO MUDAR sem verificar)

1. **`barcodes` NÃO tem UNIQUE no campo `barcode`** — um EAN pode estar em múltiplos SKUs. Não recriar essa constraint.
2. **O campo `labels_ready`** é calculado dinamicamente em `_item_dict()` no `services/picking.py` (não está no banco).
3. **Deploy automático está DESATIVADO para `main`** — apenas `nvs-production` faz deploy no Railway.
4. **A função `autoPrintLabels`** no `Picking.jsx` tem dois caminhos: direto (HTTP/localhost) e fila (HTTPS/produção). Não misturar.
5. **`warehouse_v2.db` no repo** é o banco de seed — é copiado para o volume do Railway no primeiro boot ou com `FORCE_SEED=true`.

---

## 💡 Dica para o Dev (Antigravity)

Antes de qualquer edição, pergunte-se:
- Estou mexendo em `picking.py`? → Verificar `sessions.py` e `Picking.jsx`
- Estou mexendo em `barcodes.py`? → Verificar `MasterData.jsx` e `client.js`
- Estou mexendo em `print_jobs.py`? → Verificar `agent.py` e `Picking.jsx`
- Estou mexendo em `database.py`? → Verificar se o migration block está correto

---

## 🚀 Operadores Padrão do Sistema

Master, Julio, Cris, Rafael, Luidi, Weligton, Cristofer, Renan  
*(criados automaticamente no startup se não existirem — PIN padrão: 1234)*

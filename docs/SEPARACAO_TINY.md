# Documentação Técnica: Separação Tiny ERP (NVS·WMS)

> **Última atualização:** 2026-04-23
> **Status:** Produção

---

## 1. Visão Geral

O módulo de Separação do Tiny ERP gerencia o ciclo completo de documentos de separação — desde a busca no Tiny até o envio de confirmação de volta ao ERP. O sistema utiliza um **banco local como espelho de estado**, pois o Tiny é tratado como read-only na maior parte do fluxo.

---

## 2. Ciclo de Vida de um Documento

```
Tiny (situacao=1)          ← busca manual via filtro de data
        ↓  gerar lista de picking
local: em_separacao        ← picking list criada no NVS
        ↓  todos os itens picados ou shortage
local: concluida           ← picking 100% concluído
        ↓  envio manual ou automático (a cada 5 min)
Tiny: situacao=2 + local: enviada_erp   ← Tiny confirmou OK
        ↓  Tiny processa internamente
Tiny (situacao=3)          ← embaladas/checkout (lido diretamente do Tiny)
```

### Princípio fundamental
O **Tiny é read-only**. Todo estado (em_separacao, concluida, enviada_erp, erro_envio_erp) é gerenciado localmente na tabela `tiny_separation_statuses`. A única escrita no Tiny é o envio via `separacao.alterar.situacao.php` com `situacao=2`.

---

## 3. As 5 Abas da Tela de Separação

### Aba: Aguardando Separação
- **Fonte**: API Tiny (`situacao=1`) com filtro de data
- **Carregamento**: **sob demanda** — o usuário seleciona o período e clica "Aplicar". Não carrega automaticamente ao abrir a tela.
- **Paginação**: o backend itera todas as páginas automaticamente (loop com sleep 300ms entre páginas respeitando rate limit)
- **Ação disponível**: selecionar docs + "Gerar Lista de Separação"

### Aba: Em Separação
- **Fonte**: DB local — `tiny_separation_statuses.status = 'em_separacao'`
- **Carregamento**: automático ao abrir a tela (sem filtro de data)
- **Ação disponível**: reverter para aguardando, excluir rastreamento

### Aba: Separadas
- **Fonte**: DB local — `tiny_separation_statuses.status = 'concluida'`
- **Carregamento**: automático
- **Ações disponíveis**: "Enviar para ERP" (azul), reverter para aguardando, excluir rastreamento

### Aba: Enviadas ERP
- **Fonte**: DB local — `tiny_separation_statuses.status IN ('enviada_erp', 'erro_envio_erp')`
- **Badges**: ✅ Enviado (violeta) / ❌ Erro (vermelho) por linha
- **Drawer**: mostra "Histórico de Envios ERP" com timeline (data, modo auto/manual, mensagem de erro)
- **Ação disponível**: "Re-enviar" para tentar novamente

### Aba: Embaladas/Checkout
- **Fonte**: API Tiny (`situacao=3`) com filtro de data
- **Read-only**: sem ações

---

## 4. Fluxo de Envio ERP

### 4.1 Manual (botão "Enviar para ERP")
1. Usuário seleciona docs na aba "Separadas"
2. Clica "Enviar para ERP" (azul)
3. Frontend chama `POST /api/tiny/separation-statuses/enviar-erp` com `triggered_by: "manual"`
4. Para cada doc, backend chama `separacao.alterar.situacao.php` com `situacao=2`
5. Resposta OK → `status = "enviada_erp"` + log de sucesso
6. Resposta não-OK → `status = "erro_envio_erp"` + log de erro
7. Frontend notifica: "X enviado(s), Y com erro"

### 4.2 Automático (scheduler)
- Job `erp_sync_loop` em `services/sync_engine.py`
- Roda a cada `ERP_SYNC_INTERVAL_SECONDS` (default: 300s = 5 min)
- Busca todos os docs com `status = 'concluida'` e tenta enviar
- `triggered_by = "auto"` nos logs
- Ativado junto com o scheduler principal quando `ENABLE_LOCAL_SYNC_SCHEDULER=true`

### 4.3 Parsing da resposta Tiny
O `TinyService._post` retorna o conteúdo interno do `retorno` já desembalado:
```python
# CORRETO — suporta ambos os formatos (embalado e desembalado)
retorno = resp.get("retorno", resp) if isinstance(resp, dict) else {}
ok = str(retorno.get("status", "")).upper() == "OK"

# ERRADO — assume sempre embalado
retorno = resp.get("retorno", {})  # pode retornar {} vazio
```

---

## 5. Logs de Envio ERP

### Tabela `tiny_erp_send_logs`
```
id            — PK
separation_id — ID do documento no Tiny
triggered_by  — "manual" | "auto"
status        — "success" | "error"
response_json — resposta bruta do Tiny (JSON como texto)
error_message — mensagem legível em caso de erro
sent_at       — datetime UTC
```

### Endpoint de consulta
```
GET /api/tiny/erp-send-logs/{sep_id}
→ { separation_id, logs: [{id, triggered_by, status, error_message, sent_at}] }
```

---

## 6. Arquitetura de Picking (WMS Pattern)

### Backend
- **Endpoint central**: `POST /api/tiny/picking-items/{item_id}/pick`
- **Modos**:
  - `unit`: incrementa `qty_picked` em 1 (bipe individual)
  - `box`: define `qty_picked` = `quantity` (coleta total)
  - `set`: define `qty_picked` = valor exato enviado (ajuste manual)
- **Retorno**: sempre devolve o objeto `item` completo e atualizado

### Frontend (`PickingListDetail.jsx`)
- `updateItemInState()`: sincroniza simultaneamente o estado React, as refs mutáveis e o modal aberto
- `processMainCode(code)` / `processInternalCode(code)`: helpers diretos que processam SKU/barcode sem depender do estado React (evitam stale closures)
- `autoAdvance(completedId)`: lê refs DENTRO do setTimeout(800ms) para garantir estado fresco

---

## 7. Otimizações de Performance

### Busca de separações
- **Apenas `situacao=1`** é buscada no Tiny — situações 2 e 4 são gerenciadas internamente pelo NVS
- **Busca sob demanda** — não acontece no mount da página, só quando o usuário aplica filtro de data
- **Cache de headers** (`tiny_separation_headers`) — popula automaticamente ao chamar `/separacoes`, permite que as abas locais sirvam dados sem depender do Tiny

### Cache de itens
- `tiny_separation_item_cache` — pré-aquecido em background ao abrir a lista
- TTL: 6 horas
- Evita N chamadas ao Tiny na hora de gerar a lista de picking

---

## 8. Tabelas do Módulo de Separação

| Tabela | Finalidade |
|---|---|
| `tiny_picking_lists` | Listas consolidadas geradas pelo NVS |
| `tiny_picking_list_items` | Itens por lista (sku, qty, progresso) |
| `tiny_separation_statuses` | Espelho local de status dos documentos |
| `tiny_separation_headers` | Cache de campos de display (numero, destinatario, etc.) |
| `tiny_separation_item_cache` | Cache de itens por separação (TTL 6h) |
| `tiny_erp_send_logs` | Auditoria de envios para o Tiny ERP |

---

## 9. Variáveis de Ambiente Relacionadas

| Variável | Default | Descrição |
|---|---|---|
| `TINY_API_TOKEN` | — | Token da API Tiny (obrigatório) |
| `ENABLE_OLIST_SYNC` | `true` | Push de status ao picar itens |
| `ENABLE_TINY_WEBHOOK` | `true` | Recebe eventos do Tiny |
| `ENABLE_LOCAL_SYNC_SCHEDULER` | `false` | Ativa scheduler (inclui ERP auto-send) |
| `ERP_SYNC_INTERVAL_SECONDS` | `300` | Intervalo do job ERP auto-send |

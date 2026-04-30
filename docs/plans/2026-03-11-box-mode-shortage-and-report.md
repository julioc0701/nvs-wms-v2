# Design: Modo Caixa com Falta + Relatório de Faltas

**Data:** 2026-03-11
**Status:** Aprovado

---

## Contexto

Duas melhorias relacionadas ao controle de falta de estoque:

1. **Modo Caixa com quantidade parcial** — ao bipar em modo Caixa, o operador informa quantas unidades encontrou. Se menos que o total, a diferença é registrada como falta automaticamente.

2. **Relatório de Faltas no Supervisor** — nova tela listando todos os SKUs com falta, agregados das sessões concluídas.

---

## Feature 1 — Modo Caixa com quantidade parcial

### Fluxo

1. Operador bipa código em modo Caixa
2. Sistema abre dialog **"Quantidade Encontrada"** (antes de qualquer chamada API)
3. Dialog exibe: SKU + descrição + "necessário: N"
4. Input numérico pré-preenchido com `qty_required`, min=0, max=`qty_required`
5. Ao confirmar:
   - `qty === qty_required` → `api.scanBox(code)` → completa + imprime N etiquetas
   - `0 < qty < qty_required` → `api.shortage(item.sku, qty)` → parcial + imprime qty etiquetas
   - `qty === 0` → `api.outOfStock(item.sku)` → sem estoque, sem etiquetas

### Decisões técnicas

- **Zero mudanças no backend** — usa endpoints existentes: `scan-box`, `shortage`, `out-of-stock`
- Dialog inline em `Picking.jsx` (sem novo componente separado)
- Após shortage/outOfStock: mesmo comportamento dos botões FALTA e SEM ESTOQUE existentes
- O dialog só aparece quando `item !== null` (há item ativo na tela)

### Arquivo alterado

- `frontend/src/pages/Picking.jsx`

---

## Feature 2 — Relatório de Faltas

### Backend

**Novo endpoint:** `GET /sessions/shortage-report`
**Arquivo:** `backend/routers/sessions.py`

- Busca `PickingItem` onde `shortage_qty > 0` e `session.status == 'completed'`
- Agrega por SKU: soma `shortage_qty` de todas as sessões concluídas
- Retorna `[{ sku, description, shortage_qty }]` ordenado por `shortage_qty DESC`

### Frontend

**Nova página:** `frontend/src/pages/ShortageReport.jsx`
- Mesma estrutura visual de `MasterData.jsx`
- Tabela: SKU | Descrição | Qtd Faltante
- Valor faltante em vermelho negrito
- Botão "← Supervisor" para voltar

**Nova rota:** `/shortage-report` em `App.jsx`

**Novo card em `Supervisor.jsx`:**
- Idêntico ao card "Master Data — Produtos Cadastrados"
- Botão "⚠ Ver Faltas" → navega para `/shortage-report`

**Novo método em `client.js`:**
```javascript
getShortageReport: () => req('GET', '/sessions/shortage-report'),
```

### Arquivos alterados

- `backend/routers/sessions.py` — novo endpoint
- `frontend/src/pages/ShortageReport.jsx` — nova página
- `frontend/src/pages/Supervisor.jsx` — novo card
- `frontend/src/App.jsx` — nova rota
- `frontend/src/api/client.js` — novo método

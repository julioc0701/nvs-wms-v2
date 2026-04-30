# Box Mode Shortage + Relatório de Faltas — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** (1) Modo Caixa sempre abre um dialog de quantidade — se parcial, registra falta automaticamente. (2) Nova página de Relatório de Faltas no Supervisor mostrando SKUs com falta das sessões concluídas.

**Architecture:** Feature 1 é puramente frontend (Picking.jsx), usando os endpoints existentes `shortage` e `out-of-stock`. Feature 2 adiciona um endpoint no backend (`GET /sessions/shortage-report`) e uma nova página React (`ShortageReport.jsx`) com card no Supervisor.

**Tech Stack:** React + Vite (frontend), FastAPI + SQLAlchemy (backend), Tailwind CSS, SQLite

---

## Task 1: Dialog de quantidade no Modo Caixa (Picking.jsx)

**Files:**
- Modify: `frontend/src/pages/Picking.jsx`

### Step 1: Interceptar o scan em modo Caixa antes de chamar a API

Em `handleScan`, quando `scanMode === 'box'` e há `item` ativo, em vez de chamar `api.scanBox` diretamente, abrir o dialog `box_qty`.

Localizar o bloco atual (aprox. linha 143-148):
```javascript
const res = scanMode === 'box'
  ? await api.scanBox(sessionId, code, operator.id, focusSku || null)
  : await api.scan(sessionId, code, operator.id, focusSku || null)

updateFromResponse(res, code)
```

Substituir por:
```javascript
if (scanMode === 'box' && item) {
  // Abre dialog para o operador informar a quantidade antes de commitar
  setDialog({ type: 'box_qty', data: { code } })
  return
}

const res = await api.scan(sessionId, code, operator.id, focusSku || null)
updateFromResponse(res, code)
```

### Step 2: Criar o handler `handleBoxQtyConfirm`

Adicionar logo após `handleAddBarcode` (aprox. linha 273):

```javascript
async function handleBoxQtyConfirm(qty) {
  const { code } = dialog.data
  setDialog(null)
  try {
    if (qty === 0) {
      // Sem estoque
      const res = await api.outOfStock(sessionId, item.sku, operator.id)
      setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
      if (focusSku) {
        goBackToItems()
      } else {
        setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
        const s = await api.getSession(sessionId)
        setSession(s)
        setItem(s.current_item)
        if (!s.current_item) api.getItems(sessionId).then(setAllItems)
        focusInput()
      }
    } else if (qty < item.qty_required) {
      // Falta parcial
      const res = await api.shortage(sessionId, item.sku, qty, operator.id)
      setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
      if (focusSku) {
        goBackToItems()
      } else {
        setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
        const s = await api.getSession(sessionId)
        setSession(s)
        setItem(s.current_item)
        if (!s.current_item) api.getItems(sessionId).then(setAllItems)
        focusInput()
      }
    } else {
      // Quantidade completa — usa scanBox para validar o código de barras
      const res = await api.scanBox(sessionId, code, operator.id, focusSku || null)
      updateFromResponse(res, code)
    }
  } catch (err) {
    triggerFlash('error')
    focusInput()
  }
}
```

### Step 3: Adicionar o dialog `box_qty` no JSX

Adicionar após o dialog `wrong_session` (antes do `wrong_sku`):

```jsx
{dialog?.type === 'box_qty' && item && (
  <BoxQtyDialog
    item={item}
    onConfirm={handleBoxQtyConfirm}
    onCancel={() => { setDialog(null); focusInput() }}
  />
)}
```

### Step 4: Criar o componente `BoxQtyDialog` no final do arquivo

Adicionar antes do `function CompletionSummary`:

```jsx
function BoxQtyDialog({ item, onConfirm, onCancel }) {
  const [qty, setQty] = useState(item.qty_required)

  function handleConfirm() {
    const n = Math.max(0, Math.min(item.qty_required, Number(qty) || 0))
    onConfirm(n)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-full flex flex-col gap-6">
        <h2 className="text-2xl font-bold text-center">Quantidade Encontrada</h2>
        <div className="bg-gray-50 border-2 border-gray-200 rounded-xl p-4 text-center">
          <p className="font-mono font-bold text-xl">{item.sku}</p>
          {item.description && (
            <p className="text-gray-500 text-sm mt-1">{item.description}</p>
          )}
          <p className="text-gray-400 text-xs mt-2">Necessário: {item.qty_required} unidades</p>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
            Quantas você encontrou?
          </label>
          <input
            type="number"
            min={0}
            max={item.qty_required}
            value={qty}
            onChange={e => setQty(e.target.value)}
            onFocus={e => e.target.select()}
            autoFocus
            className="text-center text-4xl font-bold border-2 border-gray-300 focus:border-blue-500 rounded-xl py-4 outline-none"
          />
          {Number(qty) < item.qty_required && Number(qty) > 0 && (
            <p className="text-orange-600 text-sm text-center">
              ⚠ {item.qty_required - Number(qty)} unidades serão registradas como falta
            </p>
          )}
          {Number(qty) === 0 && (
            <p className="text-red-600 text-sm text-center">
              ✗ Item será marcado como sem estoque
            </p>
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={onCancel}
            className="py-4 rounded-xl border-2 border-gray-300 text-lg font-medium hover:bg-gray-100"
          >
            CANCELAR
          </button>
          <button
            onClick={handleConfirm}
            className="py-4 rounded-xl bg-blue-600 text-white text-lg font-bold hover:bg-blue-700"
          >
            CONFIRMAR
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Nota:** O import de `useState` já existe no arquivo.

### Step 5: Verificar no preview

1. Ativar modo Caixa na tela de picking
2. Bipar um código válido → dialog deve abrir com qty_required
3. Testar 3 cenários:
   - Confirmar com qty cheio → item concluído + imprime etiquetas
   - Reduzir qty → item parcial (falta registrada)
   - Colocar 0 → sem estoque

### Step 6: Commit

```bash
git add frontend/src/pages/Picking.jsx
git commit -m "feat: modo caixa abre dialog de quantidade — falta registrada automaticamente"
```

---

## Task 2: Endpoint backend — Relatório de Faltas

**Files:**
- Modify: `backend/routers/sessions.py`

### Step 1: Adicionar o endpoint no final do arquivo sessions.py

```python
@router.get("/shortage-report")
def shortage_report(db: DBSession = Depends(get_db)):
    """
    Retorna todos os SKUs com falta (shortage_qty > 0) das sessões concluídas,
    agregados por SKU com a soma total de unidades faltantes.
    """
    from sqlalchemy import func

    rows = (
        db.query(
            PickingItem.sku,
            PickingItem.description,
            func.sum(PickingItem.shortage_qty).label("total_shortage"),
        )
        .join(Session, Session.id == PickingItem.session_id)
        .filter(
            Session.status == "completed",
            PickingItem.shortage_qty > 0,
        )
        .group_by(PickingItem.sku, PickingItem.description)
        .order_by(func.sum(PickingItem.shortage_qty).desc())
        .all()
    )

    return [
        {"sku": r.sku, "description": r.description, "shortage_qty": r.total_shortage}
        for r in rows
    ]
```

**Atenção:** Este endpoint deve ser adicionado ANTES do endpoint `/{session_id}` genérico para evitar conflito de rota. Verificar a ordem dos endpoints no arquivo.

### Step 2: Verificar no backend

Após reiniciar o backend, acessar:
`http://localhost:8001/api/sessions/shortage-report`

Deve retornar uma lista JSON (vazia se não há faltas ainda, ou com dados se houver sessões concluídas com falta).

### Step 3: Commit

```bash
git add backend/routers/sessions.py
git commit -m "feat: endpoint GET /sessions/shortage-report"
```

---

## Task 3: Método na API do frontend + nova rota

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/App.jsx`

### Step 1: Adicionar método em client.js

No bloco `// Sessions`, adicionar após `findByBarcode`:

```javascript
getShortageReport: () => req('GET', '/sessions/shortage-report'),
```

### Step 2: Adicionar rota em App.jsx

Ler o arquivo `frontend/src/App.jsx` para ver a estrutura atual, então:
- Importar `ShortageReport` (ainda não existe, será criado no Task 4)
- Adicionar rota `/shortage-report`

```jsx
import ShortageReport from './pages/ShortageReport'
// ...
<Route path="/shortage-report" element={<ShortageReport />} />
```

### Step 3: Commit

```bash
git add frontend/src/api/client.js frontend/src/App.jsx
git commit -m "feat: rota e metodo API para relatorio de faltas"
```

---

## Task 4: Página ShortageReport.jsx

**Files:**
- Create: `frontend/src/pages/ShortageReport.jsx`

### Step 1: Criar a página

```jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

export default function ShortageReport() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getShortageReport()
      .then(setItems)
      .finally(() => setLoading(false))
  }, [])

  const totalShortage = items.reduce((s, i) => s + i.shortage_qty, 0)

  return (
    <div className="min-h-screen bg-gray-100 p-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold">Relatório de Faltas</h1>
          <p className="text-gray-500 text-sm mt-1">
            SKUs com falta de estoque nas listas concluídas
          </p>
        </div>
        <button
          onClick={() => navigate('/supervisor')}
          className="text-blue-500 hover:underline text-lg"
        >
          ← Supervisor
        </button>
      </div>

      <div className="bg-white rounded-2xl shadow p-6">
        {loading && (
          <p className="text-center text-gray-400 py-8">Carregando...</p>
        )}

        {!loading && items.length === 0 && (
          <p className="text-center text-gray-400 py-12 text-xl">
            ✓ Nenhuma falta registrada nas listas concluídas.
          </p>
        )}

        {!loading && items.length > 0 && (
          <>
            <div className="flex justify-between items-center mb-4">
              <p className="text-sm text-gray-500">
                {items.length} SKU{items.length !== 1 ? 's' : ''} com falta
              </p>
              <p className="text-sm font-semibold text-red-600">
                Total faltante: {totalShortage} unidades
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-gray-200 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    <th className="pb-3 pr-4">SKU</th>
                    <th className="pb-3 pr-4">Descrição</th>
                    <th className="pb-3 text-right text-red-500">Qtd Faltante</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {items.map(item => (
                    <tr key={item.sku} className="hover:bg-gray-50">
                      <td className="py-3 pr-4 font-mono font-semibold whitespace-nowrap">
                        {item.sku}
                      </td>
                      <td className="py-3 pr-4 text-gray-600">
                        {item.description || '—'}
                      </td>
                      <td className="py-3 text-right">
                        <span className="font-bold text-red-600 text-base">
                          -{item.shortage_qty}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
```

### Step 2: Verificar no preview

Navegar para `/shortage-report`. Deve carregar a tabela (ou mensagem vazia se não há faltas).

### Step 3: Commit

```bash
git add frontend/src/pages/ShortageReport.jsx
git commit -m "feat: pagina de relatorio de faltas"
```

---

## Task 5: Card no Supervisor

**Files:**
- Modify: `frontend/src/pages/Supervisor.jsx`

### Step 1: Adicionar card após o card "Master Data — Produtos Cadastrados"

Localizar o card existente (aprox. linha 189-203):
```jsx
{/* Master Data Viewer */}
<div className="bg-white rounded-2xl shadow p-6 flex justify-between items-center">
  ...
</div>
```

Adicionar logo após:

```jsx
{/* Shortage Report */}
<div className="bg-white rounded-2xl shadow p-6 flex justify-between items-center">
  <div>
    <h2 className="text-2xl font-bold">Relatório de Faltas</h2>
    <p className="text-gray-500 text-sm mt-0.5">
      SKUs com falta de estoque consolidados das listas concluídas.
    </p>
  </div>
  <button
    onClick={() => navigate('/shortage-report')}
    className="py-3 px-6 bg-red-600 text-white rounded-xl text-sm font-bold hover:bg-red-700 whitespace-nowrap"
  >
    ⚠ Ver Faltas
  </button>
</div>
```

### Step 2: Verificar no preview

No Supervisor, o novo card deve aparecer com botão "⚠ Ver Faltas" que navega para `/shortage-report`.

### Step 3: Commit final

```bash
git add frontend/src/pages/Supervisor.jsx
git commit -m "feat: card de relatorio de faltas no supervisor"
```

---

## Verificação completa

1. **Modo Caixa parcial:**
   - Entrar numa lista com um item de qty=4
   - Ativar modo Caixa, bipar o código
   - Dialog abre com valor 4 pré-preenchido
   - Mudar para 2 → aviso "2 unidades serão registradas como falta"
   - Confirmar → item fica `partial`, 2 etiquetas impressas
   - Mudar para 0 → aviso "sem estoque" → confirmar → item `out_of_stock`

2. **Relatório de Faltas:**
   - Concluir uma lista com pelo menos um item de falta
   - Supervisor → card "Relatório de Faltas" → "⚠ Ver Faltas"
   - Tabela mostra o SKU, descrição e quantidade faltante em vermelho

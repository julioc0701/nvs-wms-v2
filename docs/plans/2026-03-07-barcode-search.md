# Barcode Search on Operator Screen — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let operators scan any barcode from the session-select screen and be taken directly to the picking screen for that item, or shown a clear message if the item is unavailable.

**Architecture:** New backend endpoint resolves barcode → SKU → finds best matching session (highest qty_required), returns structured action. Frontend adds a scanner-ready input to SessionSelect that reads the action and either navigates or shows an inline status card.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React + React Router + Tailwind (frontend)

---

### Task 1: Backend — `GET /sessions/find-by-barcode`

**Files:**
- Modify: `backend/routers/sessions.py` (add endpoint at the bottom, before nothing — append)

**Step 1: Add the endpoint**

Append to `backend/routers/sessions.py` (after the last existing route):

```python
@router.get("/find-by-barcode")
def find_by_barcode(
    barcode: str = Query(...),
    operator_id: int = Query(...),
    db: DBSession = Depends(get_db),
):
    """
    Locate a picking item by barcode across all active sessions.
    Returns the best match (highest qty_required) with an action hint.

    Actions:
      open             — item is pending/in_progress, session available to this operator
      already_done     — item is complete/partial/out_of_stock
      in_progress_other — session is claimed by a different operator
      not_found        — barcode not in the Barcode table
      not_in_sessions  — SKU exists but not in any active session
    """
    from fastapi import Query as Q  # already imported at module top, just here for clarity

    # 1. Resolve barcode → SKU
    bc = db.query(Barcode).filter(Barcode.barcode == barcode).first()
    if not bc:
        return {"action": "not_found", "barcode": barcode}

    sku = bc.sku

    # 2. Find all items with this SKU in non-completed sessions, best first
    rows = (
        db.query(PickingItem, Session, Operator)
        .join(Session, Session.id == PickingItem.session_id)
        .outerjoin(Operator, Operator.id == Session.operator_id)
        .filter(
            PickingItem.sku == sku,
            Session.status != "completed",
        )
        .order_by(PickingItem.qty_required.desc())
        .all()
    )

    if not rows:
        return {"action": "not_in_sessions", "sku": sku, "barcode": barcode}

    item, session, operator = rows[0]

    match = {
        "session_id": session.id,
        "session_code": session.session_code,
        "item_status": item.status,
        "qty_required": item.qty_required,
        "qty_picked": item.qty_picked,
        "description": item.description,
        "operator_id": operator.id if operator else None,
        "operator_name": operator.name if operator else None,
    }

    # 3. Determine action
    terminal = {"complete", "partial", "out_of_stock"}
    if item.status in terminal:
        action = "already_done"
    elif operator and operator.id != operator_id:
        action = "in_progress_other"
    else:
        action = "open"

    return {"action": action, "sku": sku, "barcode": barcode, "best_match": match}
```

Also add `Query` to the existing import line at the top of the file if not already there:
```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
```

**Step 2: Manual verification**

With the backend running on `localhost:8001`, test in browser or curl:

```bash
# Should return not_found
curl "http://localhost:8001/api/sessions/find-by-barcode?barcode=FAKE&operator_id=1"

# With a real barcode (replace with one from your test data)
curl "http://localhost:8001/api/sessions/find-by-barcode?barcode=7897172029080&operator_id=1"
```

Expected: JSON with `action` field set correctly.

**Step 3: Commit**

```bash
git add backend/routers/sessions.py
git commit -m "feat: add GET /sessions/find-by-barcode endpoint"
```

---

### Task 2: Frontend API client

**Files:**
- Modify: `frontend/src/api/client.js`

**Step 1: Add `findByBarcode` to the api object**

In `frontend/src/api/client.js`, inside the `api` object, after `reopenSession`:

```javascript
findByBarcode: (barcode, operatorId) =>
  req('GET', `/sessions/find-by-barcode?barcode=${encodeURIComponent(barcode)}&operator_id=${operatorId}`),
```

**Step 2: Verify**

Open browser console on `localhost:${VITE_PORT}`, log in as any operator, then:
```javascript
// In console — replace with real operator id and barcode
api.findByBarcode('7897172029080', 1).then(console.log)
```

Expected: object with `action` key.

**Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: add findByBarcode to api client"
```

---

### Task 3: Frontend — barcode search in SessionSelect

**Files:**
- Modify: `frontend/src/pages/SessionSelect.jsx`

**Step 1: Add state and search handler**

At the top of the `SessionSelect` component, add the new state variables and refs after the existing `useState` declarations:

```javascript
import { useEffect, useRef, useState } from 'react'
```

After `const operator = ...`:

```javascript
const [searchBarcode, setSearchBarcode] = useState('')
const [searchResult, setSearchResult] = useState(null)  // null | result object
const [searching, setSearching] = useState(false)
const searchRef = useRef()
const dismissTimer = useRef()
```

**Step 2: Add auto-focus effect**

After the existing `useEffect`:

```javascript
// Auto-focus barcode input on mount (scanner-ready)
useEffect(() => {
  searchRef.current?.focus()
}, [])
```

**Step 3: Add the search handler function**

After the `claim` function:

```javascript
async function handleBarcodeSearch(e) {
  if (e.key !== 'Enter' || !searchBarcode.trim()) return
  const code = searchBarcode.trim()
  setSearchBarcode('')
  setSearching(true)
  setSearchResult(null)
  clearTimeout(dismissTimer.current)

  try {
    const result = await api.findByBarcode(code, operator.id)

    if (result.action === 'open') {
      const { session_id, operator_id: sessionOp } = result.best_match
      // Claim session if it has no operator yet
      if (!sessionOp) {
        await api.claimSession(session_id, operator.id)
      }
      navigate(`/picking/${session_id}?sku=${encodeURIComponent(result.sku)}`)
      return
    }

    setSearchResult(result)
    // Auto-dismiss after 4 seconds
    dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
  } catch {
    setSearchResult({ action: 'error' })
    dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
  } finally {
    setSearching(false)
    searchRef.current?.focus()
  }
}
```

**Step 4: Add the search UI block**

In the JSX, replace the opening `<div className="min-h-screen p-8 max-w-2xl mx-auto">` section — insert the search block right after the header `</div>` (after the `← Sair` button div):

```jsx
{/* Barcode search */}
<div className="mb-8">
  <input
    ref={searchRef}
    type="text"
    value={searchBarcode}
    onChange={e => setSearchBarcode(e.target.value)}
    onKeyDown={handleBarcodeSearch}
    placeholder="Bipar código de barras para localizar item..."
    className="w-full border-2 border-gray-300 focus:border-blue-500 rounded-2xl px-5 py-4 text-xl outline-none transition-colors"
    disabled={searching}
  />

  {/* Result card */}
  {searchResult && (
    <div className={`mt-3 rounded-2xl px-5 py-4 text-base font-medium ${
      searchResult.action === 'already_done'
        ? 'bg-orange-50 border-2 border-orange-300 text-orange-800'
        : searchResult.action === 'in_progress_other'
        ? 'bg-yellow-50 border-2 border-yellow-300 text-yellow-800'
        : 'bg-red-50 border-2 border-red-300 text-red-800'
    }`}>
      {searchResult.action === 'already_done' && (() => {
        const m = searchResult.best_match
        return (
          <>
            <p className="font-bold text-lg">✓ Item já concluído</p>
            <p className="mt-1">
              <strong>{searchResult.sku}</strong> foi concluído na lista{' '}
              <strong>{m.session_code}</strong> ({m.qty_picked}/{m.qty_required} separados)
            </p>
          </>
        )
      })()}

      {searchResult.action === 'in_progress_other' && (() => {
        const m = searchResult.best_match
        return (
          <>
            <p className="font-bold text-lg">🔒 Item em separação por outro operador</p>
            <p className="mt-1">
              <strong>{searchResult.sku}</strong> está sendo separado por{' '}
              <strong>{m.operator_name}</strong> na lista <strong>{m.session_code}</strong>
            </p>
          </>
        )
      })()}

      {(searchResult.action === 'not_found' || searchResult.action === 'not_in_sessions') && (
        <>
          <p className="font-bold text-lg">✗ Código de barras não encontrado</p>
          <p className="mt-1 text-sm">
            {searchResult.action === 'not_in_sessions'
              ? `SKU "${searchResult.sku}" não está em nenhuma lista ativa.`
              : 'Este código não está cadastrado no sistema.'}
          </p>
        </>
      )}

      {searchResult.action === 'error' && (
        <p className="font-bold">✗ Erro ao consultar — tente novamente</p>
      )}
    </div>
  )}
</div>
```

**Step 5: Manual verification**

1. Open `localhost:${VITE_PORT}`, log in as operator
2. Scan/type a barcode for an available item → should navigate to picking with the SKU focused
3. Scan/type a barcode for a completed item → should show orange card
4. Scan/type a barcode for an item being worked by another operator → should show yellow card
5. Scan/type an unknown barcode → should show red card
6. Each card should disappear after 4 seconds
7. The input should regain focus after each search

**Step 6: Commit**

```bash
git add frontend/src/pages/SessionSelect.jsx
git commit -m "feat: barcode search on operator screen with smart routing"
```

---

### Task 4: Push to Railway

```bash
git push origin main
```

Wait for Railway deploy. Verify on production URL.

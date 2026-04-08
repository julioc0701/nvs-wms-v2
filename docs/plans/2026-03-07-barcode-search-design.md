# Design: Barcode Search on Operator Screen

**Date:** 2026-03-07
**Status:** Approved

## Problem

Operators currently must navigate manually through session lists to find which list contains a given item. This is slow. Operators need to scan a barcode and be taken directly to the picking screen for that item.

## Requirements

- Barcode search input on the operator screen (SessionSelect)
- On scan: locate the item across all active sessions
- If the same SKU is in multiple sessions, open the one with the highest `qty_required`
- If available: claim session if needed, navigate to picking in focus mode (`?sku=SKU`)
- If already done: show message with session code and quantities
- If in progress by another operator: show who has it and in which list
- Messages auto-dismiss after 4 seconds

## Approach

**New dedicated backend endpoint** (`GET /sessions/find-by-barcode`).
Single request from frontend. All logic in backend. Clean, fast, reusable.

## Backend

### `GET /sessions/find-by-barcode?barcode=X&operator_id=Y`

**Location:** `backend/routers/sessions.py`

**Logic:**
1. Resolve barcode → SKU via existing `resolve_barcode()`
2. Query all `PickingItem` rows with that SKU joined to `Session` and `Operator`
3. Filter: session status not `completed`
4. Sort: `qty_required DESC` (highest first = best match)
5. Determine action from best match:

| Condition | `action` |
|---|---|
| Barcode not in Barcode table | `not_found` |
| SKU not in any active session | `not_in_sessions` |
| Item terminal (complete/partial/out_of_stock) | `already_done` |
| Session has a different operator | `in_progress_other` |
| Session is open or owned by current operator | `open` |

**Response:**
```json
{
  "action": "open",
  "sku": "VEOX",
  "best_match": {
    "session_id": 14,
    "session_code": "L14",
    "item_status": "pending",
    "qty_required": 30,
    "qty_picked": 0,
    "description": "Viseira Transparente...",
    "operator_id": null,
    "operator_name": null
  }
}
```

## Frontend

### `client.js`
Add: `findByBarcode(barcode, operatorId)`

### `SessionSelect.jsx`

Add barcode search input below the operator name header. Auto-focused on mount (scanner-ready).

**On Enter/scan:**
- Call `api.findByBarcode(barcode, operator.id)`
- Clear input
- Handle result:

| `action` | Behavior |
|---|---|
| `open` | If session has no operator → `claimSession()` first. Then navigate to `/picking/{session_id}?sku={sku}` |
| `already_done` | Show orange card: "✓ VEOX já concluído na lista L14 (30/30 separados)" |
| `in_progress_other` | Show yellow card: "🔒 VEOX está sendo separado por João na lista L14" |
| `not_found` / `not_in_sessions` | Show red card: "Código de barras não encontrado" |

Result card auto-dismisses after 4 seconds or on next scan.

## Files Changed

| File | Change |
|---|---|
| `backend/routers/sessions.py` | New `GET /find-by-barcode` endpoint |
| `frontend/src/api/client.js` | New `findByBarcode()` function |
| `frontend/src/pages/SessionSelect.jsx` | Barcode search input + result cards |

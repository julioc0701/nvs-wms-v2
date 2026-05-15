# Revert doc no Tiny ao desfazer bip pós-envio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao desfazer/alterar coleta de item após o doc ter sido enviado ao Tiny como separado, reverter automaticamente no Tiny (situacao=1) com debounce, atualizar status local e avisar o operador em caso de falha.

**Architecture:** Reescrever `_check_and_advance_doc_statuses` em `backend/routers/tiny.py` pra reavaliar docs `enviada_erp`/`erro_envio_erp` quando o estado dos itens diverge de "concluida". Adicionar coroutine de revert com debounce em memória (asyncio). Estender `/tracked-separacoes` com último log de revert pro front mostrar toast.

**Tech Stack:** FastAPI (Python 3.12, asyncio), SQLAlchemy, React 18, projeto sem suíte de testes — verificação por smoke test manual.

**Spec:** [docs/superpowers/specs/2026-05-15-revert-doc-enviado-design.md](../specs/2026-05-15-revert-doc-enviado-design.md)

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `backend/routers/tiny.py` | Lógica de status + revert + endpoint tracked | Modify |
| `frontend/src/pages/SeparacaoOlist.jsx` | Toast de erro de revert | Modify |

Nenhum arquivo novo. Toda lógica de revert vive em `tiny.py` pra não pulverizar contexto. Debounce em memória (módulo-level dict) — aceitável porque processo único.

---

## Pré-execução

- Branch atual: `claude/hungry-jepsen-3762db` (worktree). User edita no main dir.
- DB schema: nenhuma migração. `TinyErpSendLog.triggered_by` já é string livre — aceita `"revert"`.
- Sem testes automatizados. Verificação: smoke test manual ao final.

---

### Task 1: Liberar transições a partir de `enviada_erp`/`erro_envio_erp` em `_check_and_advance_doc_statuses`

**Files:**
- Modify: `backend/routers/tiny.py:867-944` (função `_check_and_advance_doc_statuses`)

- [ ] **Step 1: Ler a função atual**

Confirmar que o bloco `if record.status in IMMUTABLE: continue` existe e tem `IMMUTABLE = {"enviada_erp", "erro_envio_erp"}`.

- [ ] **Step 2: Substituir o bloco IMMUTABLE pela transição condicional**

Localizar em `backend/routers/tiny.py` o trecho:

```python
        if record:
            if record.status in IMMUTABLE:
                continue
            if record.status != target:
                old = record.status
                record.status = target
                log.info(f"DOC_STATUS sep_id={sep_id} list_id={list_id} {old} → {target}")
                if target == "concluida":
                    newly_concluded.append(sep_id)
```

Substituir por:

```python
        if record:
            if record.status in IMMUTABLE:
                # Doc já está como "separado" no Tiny. Só reage se a nova
                # avaliação for diferente de "concluida" (ou seja, precisamos
                # voltar atrás no Tiny). Se target == "concluida", nada a fazer.
                if target == "concluida":
                    continue
                old = record.status
                record.status = target
                log.info(f"DOC_STATUS_REVERT sep_id={sep_id} list_id={list_id} {old} → {target}")
                _schedule_revert(sep_id)
                continue
            if record.status != target:
                old = record.status
                record.status = target
                log.info(f"DOC_STATUS sep_id={sep_id} list_id={list_id} {old} → {target}")
                if target == "concluida":
                    newly_concluded.append(sep_id)
```

- [ ] **Step 3: Verificar sintaxe**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && python -m py_compile backend/routers/tiny.py`
Expected: sem output (sem erro).

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(tiny): permite reavaliar docs enviada_erp/erro_envio_erp para acionar revert"
```

(Função `_schedule_revert` ainda não existe — Task 2 cria. Compilação passa porque é só referência.)

---

### Task 2: Implementar `_revert_separation_status_to_olist` + debounce `_schedule_revert`

**Files:**
- Modify: `backend/routers/tiny.py` (adicionar após `_push_separation_status_to_olist`)

- [ ] **Step 1: Localizar `_push_separation_status_to_olist`**

Linha ~840-865. Logo após o `return` dessa função, inserir bloco novo.

- [ ] **Step 2: Adicionar struct de debounce + funções**

Inserir logo após `_push_separation_status_to_olist`:

```python
# ── Revert de docs já enviados ao Tiny (situacao 2 → 1) ──────────────────────
# Debounce em memória por sep_id: cada agendamento cancela o anterior.
# Após 2s sem nova mudança, dispara revert no Tiny.
_REVERT_PENDING: Dict[str, "asyncio.Task"] = {}
_REVERT_DEBOUNCE_SECONDS = 2.0


def _schedule_revert(sep_id: str) -> None:
    """Agenda revert do doc no Tiny com debounce.
    Se já existe task pendente pra esse sep_id, cancela e reagenda."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        log.warning(f"REVERT_DEBOUNCE sep_id={sep_id}: sem event loop, ignorado")
        return

    existing = _REVERT_PENDING.get(sep_id)
    if existing and not existing.done():
        existing.cancel()

    _REVERT_PENDING[sep_id] = loop.create_task(_revert_after_delay(sep_id))
    log.info(f"REVERT_DEBOUNCE sep_id={sep_id} agendado em {_REVERT_DEBOUNCE_SECONDS}s")


async def _revert_after_delay(sep_id: str) -> None:
    try:
        await asyncio.sleep(_REVERT_DEBOUNCE_SECONDS)
        await _revert_separation_status_to_olist(sep_id)
    except asyncio.CancelledError:
        log.info(f"REVERT_DEBOUNCE sep_id={sep_id} cancelado (nova mudança)")
    finally:
        _REVERT_PENDING.pop(sep_id, None)


async def _revert_separation_status_to_olist(sep_id: str) -> None:
    """Chama Tiny pra voltar a separação pra situacao=1 (aguardando).
    Loga sucesso/falha em TinyErpSendLog com triggered_by='revert'.
    Nunca lança — falha é registrada no log e exibida ao operador via toast."""
    if not ENABLE_OLIST_SYNC:
        log.info(f"[REVERT DRY-RUN] sep_id={sep_id} — ENABLE_OLIST_SYNC=false")
        return
    if not TINY_TOKEN:
        log.warning(f"[REVERT] sep_id={sep_id} sem TINY_TOKEN configurado")
        return

    db = SessionLocal()
    try:
        svc = TinyService(TINY_TOKEN)
        resp_json_str: Optional[str] = None
        error_msg: Optional[str] = None
        ok = False
        try:
            resp = await svc._post("separacao.alterar.situacao.php", {
                "id": sep_id,
                "situacao": 1,
            })
            resp_json_str = json.dumps(resp, ensure_ascii=False) if isinstance(resp, dict) else str(resp)
            retorno = resp.get("retorno", resp) if isinstance(resp, dict) else {}
            ok = str(retorno.get("status", "")).upper() == "OK"
            if not ok:
                error_msg = f"Tiny NOK: {resp_json_str[:300]}"
        except Exception as exc:
            error_msg = str(exc)
            log.error(f"[REVERT ERRO] sep_id={sep_id}: {error_msg}")

        db.add(TinyErpSendLog(
            separation_id=sep_id,
            triggered_by="revert",
            status="success" if ok else "error",
            response_json=resp_json_str,
            error_message=error_msg,
            sent_at=datetime.utcnow(),
        ))
        db.commit()
        if ok:
            log.info(f"[REVERT OK] sep_id={sep_id}")
    finally:
        db.close()
```

- [ ] **Step 3: Verificar imports**

No topo de `tiny.py` confirmar presença de:
- `import asyncio` ✓ (já existe linha 8)
- `import json` ✓ (já existe linha 9)
- `from datetime import datetime` ✓ (já existe)
- `from database import SessionLocal` ✓ (já existe)
- `from models import TinyErpSendLog` ✓ (já existe)
- `from typing import Optional, Dict` ✓ (já existe)

Nada a adicionar.

- [ ] **Step 4: Verificar compilação**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && python -m py_compile backend/routers/tiny.py`
Expected: sem output.

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(tiny): _revert_separation_status_to_olist com debounce de 2s"
```

---

### Task 3: `register_item_unpick` reavalia status do doc

**Files:**
- Modify: `backend/routers/tiny.py:1377-1406` (função `register_item_unpick`)

- [ ] **Step 1: Adicionar `background_tasks` à assinatura**

Localizar:
```python
@router.post("/picking-items/{item_id}/unpick")
async def register_item_unpick(item_id: int, db: Session = Depends(get_db)):
```

Substituir por:
```python
@router.post("/picking-items/{item_id}/unpick")
async def register_item_unpick(item_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
```

- [ ] **Step 2: Adicionar chamada de revalidação antes do return**

Localizar o final da função:
```python
    db.commit()
    log.info(f"UNPICK id={item_id} sku={sku} — shortage removido")
    return {"status": "success", "item": {"id": item_id, "qty_picked": 0.0, "qty_shortage": 0.0, "is_shortage": False, "notes": None}}
```

Inserir antes do `return`:
```python
    # Reavalia status dos docs — se doc estava enviada_erp e agora item não está
    # mais coletado, _check_and_advance vai detectar e disparar revert no Tiny.
    try:
        concluded_ids = _check_and_advance_doc_statuses(list_id, db)
        for sep_id in (concluded_ids or []):
            background_tasks.add_task(_push_separation_status_to_olist, sep_id)
    except Exception as ce:
        log.error(f"ERRO ao reavaliar status docs (unpick) item={item_id}: {ce}", exc_info=True)
```

Bloco final fica:
```python
    db.commit()

    try:
        concluded_ids = _check_and_advance_doc_statuses(list_id, db)
        for sep_id in (concluded_ids or []):
            background_tasks.add_task(_push_separation_status_to_olist, sep_id)
    except Exception as ce:
        log.error(f"ERRO ao reavaliar status docs (unpick) item={item_id}: {ce}", exc_info=True)

    log.info(f"UNPICK id={item_id} sku={sku} — shortage removido")
    return {"status": "success", "item": {"id": item_id, "qty_picked": 0.0, "qty_shortage": 0.0, "is_shortage": False, "notes": None}}
```

- [ ] **Step 3: Verificar compilação**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && python -m py_compile backend/routers/tiny.py`
Expected: sem output.

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(tiny): unpick reavalia status do doc (libera revert pós-envio)"
```

---

### Task 4: Endpoint `/separation-statuses/revert` aciona Tiny

**Files:**
- Modify: `backend/routers/tiny.py` (função do endpoint revert)

- [ ] **Step 1: Localizar o endpoint atual**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && rtk grep -n "separation-statuses/revert" backend/routers/tiny.py`
Capturar a linha do `@router.post`. Ler ~30 linhas da função.

- [ ] **Step 2: Identificar o bloco de delete local**

A função hoje recebe lista de `sep_ids`, deleta `TinySeparationStatus` correspondentes. Vamos manter esse comportamento e adicionar — **antes** do delete, se o status atual era `enviada_erp` ou `erro_envio_erp`, disparar `_revert_separation_status_to_olist` direto (sem debounce — é ação manual).

- [ ] **Step 3: Adicionar revert no fluxo manual**

Substituir a iteração que deleta (estrutura típica):

```python
    for sep_id in sep_ids:
        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == sep_id
        ).first()
        if record:
            db.delete(record)
```

Por:

```python
    sep_ids_to_revert_tiny: List[str] = []
    for sep_id in sep_ids:
        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == sep_id
        ).first()
        if record:
            if record.status in ("enviada_erp", "erro_envio_erp"):
                sep_ids_to_revert_tiny.append(sep_id)
            db.delete(record)

    db.commit()

    # Revert manual no Tiny — sem debounce (ação explícita)
    for sep_id in sep_ids_to_revert_tiny:
        background_tasks.add_task(_revert_separation_status_to_olist, sep_id)
```

Confirmar que o endpoint já recebe `background_tasks: BackgroundTasks`. Se não, adicionar.

- [ ] **Step 4: Verificar compilação**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && python -m py_compile backend/routers/tiny.py`

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(tiny): endpoint revert dispara situacao=1 no Tiny para docs enviados"
```

---

### Task 5: `/tracked-separacoes` retorna `last_revert_log`

**Files:**
- Modify: `backend/routers/tiny.py:447-497` (montagem do payload de tracked)

- [ ] **Step 1: Localizar a montagem de `last_erp_logs`**

Linha ~448-470. Bloco que monta dict `last_erp_logs` por separation_id (último ERP send log).

- [ ] **Step 2: Adicionar bloco análogo pra revert logs**

Logo após o bloco de `last_erp_logs`, inserir:

```python
    # Último log de revert por doc (para toast no front quando falha)
    last_revert_logs: dict = {}
    if sep_ids:
        from sqlalchemy import func as sa_func
        subq_rev = (
            db.query(
                TinyErpSendLog.separation_id,
                sa_func.max(TinyErpSendLog.sent_at).label("max_sent")
            )
            .filter(TinyErpSendLog.separation_id.in_(sep_ids))
            .filter(TinyErpSendLog.triggered_by == "revert")
            .group_by(TinyErpSendLog.separation_id)
            .subquery()
        )
        revert_logs = (
            db.query(TinyErpSendLog)
            .join(subq_rev, (TinyErpSendLog.separation_id == subq_rev.c.separation_id) &
                            (TinyErpSendLog.sent_at == subq_rev.c.max_sent))
            .filter(TinyErpSendLog.triggered_by == "revert")
            .all()
        )
        last_revert_logs = {l.separation_id: l for l in revert_logs}
```

- [ ] **Step 3: Incluir `last_revert_log` no dict de resposta**

Localizar a montagem do `result.append({...})`. Antes da chave `last_erp_log`, adicionar:

```python
            "last_revert_log": ({
                "id": rev_log.id,
                "status": rev_log.status,
                "error_message": rev_log.error_message,
                "sent_at": rev_log.sent_at.isoformat(),
            } if (rev_log := last_revert_logs.get(s.separation_id)) else None),
```

(Walrus + ternário inline). Se o estilo do arquivo não combinar com walrus, usar versão expandida:

```python
            "last_revert_log": _serialize_revert_log(last_revert_logs.get(s.separation_id)),
```

e adicionar helper no topo do arquivo. Preferir o walrus inline (1 linha, sem novo nome global).

- [ ] **Step 4: Verificar compilação**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && python -m py_compile backend/routers/tiny.py`

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(tiny): /tracked-separacoes expõe last_revert_log por doc"
```

---

### Task 6: Toast de falha de revert no front

**Files:**
- Modify: `frontend/src/pages/SeparacaoOlist.jsx` (função `fetchTrackedSeparacoes`)

- [ ] **Step 1: Localizar `fetchTrackedSeparacoes`**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && rtk grep -n "fetchTrackedSeparacoes\|trackedSeparacoes" frontend/src/pages/SeparacaoOlist.jsx | rtk head -c 600`

- [ ] **Step 2: Detectar revert logs novos com falha e exibir toast**

Após a linha onde `setTrackedSeparacoes(items)` é chamado (dentro de `fetchTrackedSeparacoes`), adicionar:

```javascript
      // Detectar reverts falhados ainda não vistos → toast vermelho
      const SEEN_KEY = 'nvs.revertLogSeenAt'
      const lastSeenStr = localStorage.getItem(SEEN_KEY) || '1970-01-01T00:00:00.000Z'
      const lastSeen = new Date(lastSeenStr).getTime()
      let maxSeen = lastSeen
      items.forEach(s => {
        const log = s.last_revert_log
        if (!log) return
        const ts = new Date(log.sent_at).getTime()
        if (ts > maxSeen) maxSeen = ts
        if (log.status === 'error' && ts > lastSeen) {
          const numero = s.numero || s.id
          notify(`Falha ao reverter doc ${numero} no Tiny — verifique manualmente`, 'error')
        }
      })
      if (maxSeen > lastSeen) {
        localStorage.setItem(SEEN_KEY, new Date(maxSeen).toISOString())
      }
```

(Confirmar que `notify` é o helper de toast desse arquivo — buscar `notify(` no topo. Se for outro nome, ajustar.)

- [ ] **Step 3: Smoke test do build**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend" && npm run build 2>&1 | rtk tail -c 500`
Expected: build sem erro.

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/pages/SeparacaoOlist.jsx
git commit -m "feat(separacao): toast vermelho ao detectar revert falhado no Tiny"
```

---

### Task 7: Smoke test manual end-to-end

**Files:** (nenhum — apenas validação)

- [ ] **Step 1: Reiniciar backend**

Backend precisa reiniciar (mudanças em tiny.py). Frontend HMR pega sozinho.

- [ ] **Step 2: Caso A — fluxo feliz (revert automático)**

1. Gera lista de picking com 1 SKU/1 nota.
2. Bipa SKU → confirma na aba "separadas" → confirma na aba "enviadas ERP" após 5 min (ou força via botão manual).
3. Doc agora está como `situacao=2` no Tiny.
4. Volta na lista, desfaz o bip (`unpick`).
5. Marca SKU como sem estoque.
6. Aguarda ~3s (debounce + chamada).
7. **Verificar:**
   - No NVS: doc aparece na coluna **"sem estoque"**.
   - No Tiny (interface web Olist): doc volta pra `aguardando separação` (situacao=1).
   - No DB: `tiny_erp_send_logs` tem entrada com `triggered_by="revert"` e `status="success"`.

- [ ] **Step 3: Caso B — debounce evita chamadas duplas**

1. Doc em `enviada_erp`.
2. Desfaz bip + marca shortage + desmarca shortage + re-bipa rapidamente (em < 2s entre cada).
3. **Verificar:** Apenas 1 chamada de revert acontece (ou nenhuma se estado final = concluida).
   - Conferir `tiny_erp_send_logs`: deve haver no máximo 1 log `triggered_by="revert"` dessa rodada.

- [ ] **Step 4: Caso C — falha de revert exibe toast**

(Difícil simular sem mockar Tiny — pular se não houver forma fácil.)

Alternativa: inserir manualmente em `tiny_erp_send_logs` uma linha com `triggered_by="revert"`, `status="error"`, `error_message="teste"`, `sent_at=now()` pra um sep_id rastreado. Recarregar a página. Toast vermelho deve aparecer 1x. Recarregar de novo → não aparece (já visto).

- [ ] **Step 5: Verificar não-regressão**

1. Fluxo normal (bipa tudo, fecha lista) continua funcionando: doc vai pra `enviadas ERP` normal.
2. Aba "sem estoque" continua mostrando docs com shortage em listas em andamento.

- [ ] **Step 6: Commit do smoke test (se houver fix)**

Se algum bug surgir nos casos acima, fix vai como commit avulso com mensagem `fix(tiny): ...`.

---

## Self-Review

**Spec coverage:**
- ✅ Triggers (unpick/report-shortage/clear-shortage/pick): Task 1 muda `_check_and_advance`, Task 3 adiciona unpick. Report-shortage e clear-shortage já chamam `_check_and_advance` no estado atual do código.
- ✅ Revert automático com debounce 2s: Task 2.
- ✅ Endpoint manual revert dispara Tiny: Task 4.
- ✅ `last_revert_log` em `/tracked-separacoes`: Task 5.
- ✅ Toast no front: Task 6.
- ✅ Smoke test manual: Task 7.

**Placeholder scan:** Nenhum TBD/TODO/"similar to". Códigos completos. Único condicional aberto: Task 5 Step 3 oferece duas variantes (walrus vs helper); pick walrus.

**Type consistency:** `_schedule_revert`, `_revert_after_delay`, `_revert_separation_status_to_olist` consistentes entre tasks. `_REVERT_PENDING` definido na Task 2 e referenciado nas mesmas funções. `last_revert_log` JSON shape consistente entre backend (Task 5) e front (Task 6).

**Scope:** 1 spec → 1 plano. Apropriado.

---

## Execution Handoff

Plan saved to [docs/superpowers/plans/2026-05-15-revert-doc-enviado.md](2026-05-15-revert-doc-enviado.md).

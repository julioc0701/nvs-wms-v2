"""Core picking business logic."""
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from models import PickingItem, Barcode, ScanEvent, Session, Label, PrintJob, Operator


def get_current_item(db: DBSession, session_id: int) -> PickingItem | None:
    """Return the first non-completed item for this session."""
    return (
        db.query(PickingItem)
        .filter(
            PickingItem.session_id == session_id,
            PickingItem.status.in_(["pending", "in_progress"]),
        )
        .order_by(PickingItem.id)
        .first()
    )


def resolve_barcode(db: DBSession, barcode: str) -> list[str]:
    """Return all SKUs for a barcode."""
    b = barcode.strip()
    entries = db.query(Barcode).filter(Barcode.barcode == b).all()
    return list(set(e.sku for e in entries))


def process_scan(
    db: DBSession,
    session_id: int,
    barcode: str,
    operator_id: int,
    focus_sku: str | None = None,
) -> dict:
    """
    Main scan handler. Returns a result dict with status and updated item state.
    Possible statuses: ok | complete | excess | unknown_barcode | wrong_sku | ambiguous_barcode
    """
    skus = resolve_barcode(db, barcode)

    # Barcode não vinculado → unknown_barcode
    if not skus:
        return {"status": "unknown_barcode", "barcode": barcode}

    # Barcode igual ao próprio SKU → rejeita (SKU não é barcode válido)
    if len(skus) == 1 and barcode.strip().upper() == skus[0].strip().upper():
        return {"status": "unknown_barcode", "barcode": barcode}

    is_barcode = True

    # --- NOVO: PRIORIDADE DE FOCO ---
    # Se temos um SKU focado, e esse código NÃO está vinculado a ele,
    # ignoramos qualquer outro SKU global para forçar o vínculo local.
    if focus_sku:
        if focus_sku.upper() not in [s.upper() for s in skus]:
            return {"status": "unknown_barcode", "barcode": barcode}
    # -------------------------------

    # Find which of these SKUs are in the current session
    items = (
        db.query(PickingItem)
        .filter(PickingItem.session_id == session_id, PickingItem.sku.in_(skus))
        .all()
    )

    if not items:
            
        # Barcode é conhecido mas pertence a SKU(s) que não estão nesta sessão
        # Pegamos o primeiro SKU para prover uma descrição de erro (legado)
        target_sku = skus[0]
        
        # --- NOVO: Tenta localizar esse SKU em outras sessões para sugerir transferência ---
        other_rows = (
            db.query(PickingItem, Session, Operator)
            .join(Session, Session.id == PickingItem.session_id)
            .outerjoin(Operator, Operator.id == Session.operator_id)
            .filter(PickingItem.sku.in_(skus), Session.status != "completed")
            .filter(PickingItem.qty_picked == 0) # Só sugere transferir o que não começou
            .order_by(PickingItem.qty_required.desc())
            .all()
        )
        if other_rows:
            other_item, other_session, other_op = other_rows[0]
            return {
                "status": "wrong_session",
                "action": "transfer_available",
                "item_id": other_item.id,
                "sku": other_item.sku,
                "owner_name": other_op.name if other_op else "Disponível",
                "barcode": barcode
            }

        target_sku = skus[0]
        bc = db.query(Barcode).filter(Barcode.barcode == barcode.strip(), Barcode.sku == target_sku).first()
        description = (bc.description if bc else None) or (
            db.query(PickingItem.description)
            .filter(PickingItem.sku == target_sku, PickingItem.description.isnot(None))
            .scalar()
        )
        return {
            "status": "wrong_session", 
            "barcode": barcode, 
            "sku": target_sku, 
            "description": description,
            "all_skus": skus
        }

    # SELECTION LOGIC for multiple SKUs for the same barcode
    if len(items) > 1 and not focus_sku:
        # If we have multiple SKUs in this session for the same barcode, and no focus_sku was provided,
        # we must ask the operator to choose.
        return {
            "status": "ambiguous_barcode",
            "barcode": barcode,
            "candidates": [_item_dict(i) for i in items]
        }

    # If we have a focus_sku, or only one match, we pick that one
    if focus_sku:
        target_focus = focus_sku.strip().upper()
        item = next((i for i in items if i.sku.upper() == target_focus), None)
        if not item:
             return {"status": "error", "message": f"SKU focado {focus_sku} não encontrado para este código"}
    else:
        item = items[0]

    # Valid scan — increment ATOMICALLY to prevent race conditions
    
    # ── REGRA DE OURO: QUEM EXECUTA É O DONO ────────────────────────────────────
    # Se o operador atual não é o dono da sessão (e a sessão já está em andamento/outra pessoa),
    # forçamos a transferência para que o item mude de lista.
    # Exceção: se a sessão estiver 'open' (sem operador ainda), o primeiro scan faz o claim normal.
    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess and sess.operator_id and sess.operator_id != operator_id:
        return {
            "status": "wrong_session",
            "action": "transfer_available",
            "item_id": item.id,
            "sku": item.sku,
            "owner_name": sess.operator.name if sess.operator else "Outro",
            "barcode": barcode
        }
    # ────────────────────────────────────────────────────────────────────────────

    from sqlalchemy import update
    stmt = (
        update(PickingItem)
        .where(PickingItem.id == item.id, PickingItem.qty_picked < PickingItem.qty_required)
        .values(
            qty_picked=PickingItem.qty_picked + 1,
            status="in_progress"
        )
    )
    res = db.execute(stmt)

    if res.rowcount == 0:
        db.refresh(item)
        if item.qty_picked >= item.qty_required:
            return {"status": "excess", "item": _item_dict(item)}
        return {"status": "error", "message": "Falha de concorrência no incremento"}

    # Atualiza a referência de item na memória com banco atualizado
    db.refresh(item)

    # Marca sessão como in_progress no primeiro scan (claim não muda mais o status)
    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess and sess.status == "open":
        sess.status = "in_progress"
        if not sess.operator_id:
            sess.operator_id = operator_id

    log_event(db, session_id, item.id, barcode, operator_id, "scan", 1)

    if item.qty_picked >= item.qty_required:
        item.status = "complete"
        item.completed_at = datetime.utcnow()
        _auto_complete_session(db, session_id)
        _create_print_job(db, session_id, item.sku, operator_id)
        db.commit()
        return {"status": "complete", "item": _item_dict(item)}

    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def process_scan_box(
    db: DBSession,
    session_id: int,
    barcode: str,
    operator_id: int,
    focus_sku: str | None = None,
) -> dict:
    """
    Box mode scan: one scan marks the entire required quantity as picked.
    Same barcode validation as process_scan (unknown_barcode / wrong_sku / excess).
    """
    skus = resolve_barcode(db, barcode)
    # Barcode não vinculado → unknown_barcode
    if not skus:
        return {"status": "unknown_barcode", "barcode": barcode}
    # Barcode igual ao próprio SKU → rejeita
    if len(skus) == 1 and barcode.strip().upper() == skus[0].strip().upper():
        return {"status": "unknown_barcode", "barcode": barcode}

    items = (
        db.query(PickingItem)
        .filter(PickingItem.session_id == session_id, PickingItem.sku.in_(skus))
        .all()
    )

    if not items:
            
        # --- NOVO: Tenta localizar esse SKU em outras sessões para sugerir transferência ---
        other_rows = (
            db.query(PickingItem, Session, Operator)
            .join(Session, Session.id == PickingItem.session_id)
            .outerjoin(Operator, Operator.id == Session.operator_id)
            .filter(PickingItem.sku.in_(skus), Session.status != "completed")
            .filter(PickingItem.qty_picked == 0)
            .order_by(PickingItem.qty_required.desc())
            .all()
        )
        if other_rows:
            other_item, other_session, other_op = other_rows[0]
            return {
                "status": "wrong_session",
                "action": "transfer_available",
                "item_id": other_item.id,
                "sku": other_item.sku,
                "owner_name": other_op.name if other_op else "Disponível",
                "barcode": barcode
            }

        return {"status": "wrong_session", "barcode": barcode, "sku": skus[0]}

    if len(items) > 1 and not focus_sku:
        return {
            "status": "ambiguous_barcode",
            "barcode": barcode,
            "candidates": [_item_dict(i) for i in items]
        }

    if focus_sku:
        item = next((i for i in items if i.sku == focus_sku), None)
        if not item:
             return {"status": "error", "message": f"SKU focado {focus_sku} não encontrado para este código"}
    else:
        item = items[0]

    sku = item.sku
    current = get_current_item(db, session_id)
    in_focus_mode = focus_sku is not None and focus_sku == sku
    if current and current.sku != sku and not in_focus_mode:
        return {
            "status": "wrong_sku",
            "scanned_sku": sku,
            "expected_sku": current.sku,
            "item": _item_dict(item),
        }

    if item.qty_picked >= item.qty_required:
        return {"status": "excess", "item": _item_dict(item)}

    # Mark full quantity as picked in one shot
    delta = item.qty_required - item.qty_picked
    if delta <= 0:
        return {"status": "excess", "item": _item_dict(item)}

    # ── REGRA DE OURO: QUEM EXECUTA É O DONO ────────────────────────────────────
    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess and sess.operator_id and sess.operator_id != operator_id:
        return {
            "status": "wrong_session",
            "action": "transfer_available",
            "item_id": item.id,
            "sku": item.sku,
            "owner_name": sess.operator.name if sess.operator else "Outro",
            "barcode": barcode
        }
    # ────────────────────────────────────────────────────────────────────────────

    from sqlalchemy import update
    stmt = (
        update(PickingItem)
        .where(PickingItem.id == item.id, PickingItem.qty_picked < PickingItem.qty_required)
        .values(
            qty_picked=PickingItem.qty_required,
            status="complete",
            completed_at=datetime.utcnow()
        )
    )
    res = db.execute(stmt)

    if res.rowcount == 0:
        db.refresh(item)
        return {"status": "excess", "item": _item_dict(item)}

    db.refresh(item)

    # Marca sessão como in_progress no primeiro scan (claim não muda mais o status)
    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess and sess.status == "open":
        sess.status = "in_progress"
        if not sess.operator_id:
            sess.operator_id = operator_id

    log_event(db, session_id, item.id, barcode, operator_id, "scan_box", delta)
    _auto_complete_session(db, session_id)
    _create_print_job(db, session_id, item.sku, operator_id)
    db.commit()
    return {"status": "complete", "item": _item_dict(item)}


def undo_last_scan(db: DBSession, session_id: int, sku: str, operator_id: int) -> dict:
    item = _get_item(db, session_id, sku)
    if not item or item.qty_picked <= 0:
        return {"status": "nothing_to_undo"}

    item.qty_picked -= 1
    if item.status in ("complete",):
        item.status = "in_progress"
        item.completed_at = None
    if item.qty_picked == 0:
        item.status = "pending"

    log_event(db, session_id, item.id, "UNDO", operator_id, "undo", -1)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def mark_shortage(db: DBSession, session_id: int, sku: str, qty_found: int, operator_id: int, notes: str | None = None) -> dict:
    item = _get_item(db, session_id, sku)
    if not item:
        return {"status": "not_found"}

    item.qty_picked = qty_found
    item.shortage_qty = item.qty_required - qty_found
    item.status = "partial"
    item.notes = notes
    item.completed_at = datetime.utcnow()

    log_event(db, session_id, item.id, "SHORTAGE", operator_id, "shortage", qty_found)
    _auto_complete_session(db, session_id)
    if item.qty_picked > 0:
        _create_print_job(db, session_id, item.sku, operator_id)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def mark_out_of_stock(db: DBSession, session_id: int, sku: str, operator_id: int, notes: str | None = None) -> dict:
    item = _get_item(db, session_id, sku)
    if not item:
        return {"status": "not_found"}

    # Preserve whatever was already scanned; mark the rest as out of stock
    item.shortage_qty = item.qty_required - item.qty_picked
    item.status = "partial" if item.qty_picked > 0 else "out_of_stock"
    item.notes = notes
    item.completed_at = datetime.utcnow()

    log_event(db, session_id, item.id, "OOS", operator_id, "out_of_stock", 0)
    _auto_complete_session(db, session_id)
    if item.qty_picked > 0:
        _create_print_job(db, session_id, item.sku, operator_id)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def reopen_item(db: DBSession, session_id: int, sku: str, operator_id: int) -> dict:
    item = _get_item(db, session_id, sku)
    if not item:
        return {"status": "not_found"}

    item.status = "in_progress" if item.qty_picked > 0 else "pending"
    item.shortage_qty = 0
    item.completed_at = None

    log_event(db, session_id, item.id, "REOPEN", operator_id, "reopen", 0)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def _auto_complete_session(db: DBSession, session_id: int):
    """Mark session as completed when all items are in a terminal state."""
    items = db.query(PickingItem).filter(PickingItem.session_id == session_id).all()
    done = {"complete", "partial", "out_of_stock"}
    if items and all(i.status in done for i in items):
        sess = db.query(Session).filter(Session.id == session_id).first()
        if sess and sess.status != "completed":
            sess.status = "completed"
            sess.completed_at = datetime.utcnow()


def reset_item(db: DBSession, session_id: int, sku: str, operator_id: int) -> dict:
    """Reset a single item back to zero — qty_picked=0, status=pending."""
    item = _get_item(db, session_id, sku)
    if not item:
        return {"status": "not_found"}

    item.qty_picked = 0
    item.shortage_qty = 0
    item.status = "pending"
    item.completed_at = None
    item.labels_printed = False

    # If session was completed, revert to in_progress
    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess and sess.status == "completed":
        sess.status = "in_progress"
        sess.completed_at = None

    log_event(db, session_id, item.id, "RESET", operator_id, "reset", 0)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def force_complete_item(db: DBSession, session_id: int, sku: str, operator_id: int) -> dict:
    """Force an item to complete — qty_picked=qty_required, status=complete."""
    item = _get_item(db, session_id, sku)
    if not item:
        return {"status": "not_found"}

    item.qty_picked = item.qty_required
    item.shortage_qty = 0
    item.status = "complete"
    item.completed_at = datetime.utcnow()
    # We do NOT call _create_print_job here because the user usually wants this 
    # when labels are already printed/handled manually.

    log_event(db, session_id, item.id, "FORCE_COMPLETE", operator_id, "force_complete", item.qty_required)
    _auto_complete_session(db, session_id)
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def update_item_notes(db: DBSession, item_id: int, notes: str | None) -> dict:
    item = db.query(PickingItem).filter(PickingItem.id == item_id).first()
    if not item:
        return {"status": "not_found"}
    item.notes = notes
    db.commit()
    return {"status": "ok", "item": _item_dict(item)}


def update_sku_notes(db: DBSession, sku: str, notes: str | None) -> dict:
    """Updates notes for all items with this SKU that have shortages."""
    db.query(PickingItem).filter(
        PickingItem.sku == sku,
        PickingItem.shortage_qty > 0
    ).update({"notes": notes}, synchronize_session=False)
    db.commit()
    return {"status": "ok", "sku": sku}


def reset_all_items(db: DBSession, session_id: int, operator_id: int) -> dict:
    """Reset every item in a session back to zero."""
    items = db.query(PickingItem).filter(PickingItem.session_id == session_id).all()
    for item in items:
        item.qty_picked = 0
        item.shortage_qty = 0
        item.status = "pending"
        item.completed_at = None
        item.labels_printed = False
        log_event(db, session_id, item.id, "RESET_ALL", operator_id, "reset_all", 0)

    sess = db.query(Session).filter(Session.id == session_id).first()
    if sess:
        sess.status = "in_progress"
        sess.completed_at = None

    db.commit()
    return {"status": "ok", "items_reset": len(items)}


def add_barcode(db: DBSession, barcode: str, sku: str, operator_id: int) -> dict:
    b = barcode.strip()
    s = sku.strip().upper()
    existing = db.query(Barcode).filter(Barcode.barcode == b, Barcode.sku == s).first()
    if existing:
        return {"status": "already_exists", "sku": existing.sku}
    
    # Check if there is a global constraint issue by catching IntegrityError
    from sqlalchemy.exc import IntegrityError
    try:
        entry = Barcode(barcode=b, sku=s, is_primary=False, added_by=operator_id)
        db.add(entry)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # If we hit a unique constraint on 'barcode', it means the DB doesn't allow ambiguity yet.
        # But we want to allow it. We might need a structural change if it's a hard UNIQUE.
        return {"status": "error", "message": f"Erro de banco de dados (provável restrição de unicidade): {str(e)}"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

    return {"status": "ok"}


def session_progress(db: DBSession, session_id: int) -> dict:
    items = db.query(PickingItem).filter(PickingItem.session_id == session_id).all()
    total_items = sum(i.qty_required for i in items)
    picked_items = sum(i.qty_picked for i in items)
    done_statuses = {"complete", "partial", "out_of_stock"}
    skus_complete = sum(1 for i in items if i.status in done_statuses)
    return {
        "items_picked": picked_items,
        "items_total": total_items,
        "skus_complete": skus_complete,
        "skus_total": len(items),
    }


def _create_print_job(db: DBSession, session_id: int, sku: str, operator_id: int) -> None:
    """
    Cria um PrintJob para o SKU recém-concluído, se houver etiquetas cadastradas.
    Não cria duplicata se já existe job PENDING ou PRINTING para o mesmo par.
    """
    # Evita duplicata em andamento
    active = (
        db.query(PrintJob)
        .filter(
            PrintJob.session_id == session_id,
            PrintJob.sku == sku,
            PrintJob.status.in_(["PENDING", "PRINTING"]),
        )
        .first()
    )
    if active:
        return

    labels = (
        db.query(Label)
        .filter(Label.session_id == session_id, Label.sku == sku)
        .order_by(Label.id)
        .all()
    )
    if not labels:
        return  # sem etiquetas cadastradas para este SKU

    zpl = "\n".join(lb.zpl_content for lb in labels if lb.zpl_content)
    job = PrintJob(
        session_id=session_id,
        sku=sku,
        zpl_content=zpl,
        operator_id=operator_id,
        status="PENDING",
    )
    db.add(job)


def log_event(db, session_id, item_id, barcode, operator_id, event_type, qty_delta):
    ev = ScanEvent(
        session_id=session_id,
        picking_item_id=item_id,
        barcode=barcode,
        operator_id=operator_id,
        event_type=event_type,
        qty_delta=qty_delta,
    )
    db.add(ev)


def _get_item(db: DBSession, session_id: int, sku: str) -> PickingItem | None:
    return (
        db.query(PickingItem)
        .filter(PickingItem.session_id == session_id, PickingItem.sku == sku)
        .first()
    )


def _item_dict(item: PickingItem) -> dict:
    return {
        "id": item.id,
        "sku": item.sku,
        "ml_code": item.ml_code,
        "description": item.description,
        "qty_required": item.qty_required,
        "qty_picked": item.qty_picked,
        "shortage_qty": item.shortage_qty,
        "status": item.status,
        "labels_ready": item.status in ("complete", "partial", "out_of_stock") and item.qty_picked > 0,
        "labels_printed": item.labels_printed,
    }
def reallocate_item(db: DBSession, item_id: int, operator_id: int) -> Session:
    """
    Moves a PickingItem and its Labels to a new "EXTRA" session for the given operator.
    Returns the newly created Session.
    """
    item = db.query(PickingItem).filter(PickingItem.id == item_id).first()
    if not item:
        raise ValueError("Item não encontrado")
    
    if item.qty_picked > 0:
        raise ValueError("Não é possível transferir um item que já possui unidades coletadas")

    old_session = db.query(Session).filter(Session.id == item.session_id).first()
    
    # Create the new EXTRA session
    new_code = f"EXT-{old_session.session_code}-{datetime.utcnow().strftime('%M%S')}"
    new_sess = Session(
        session_code=new_code,
        operator_id=operator_id,
        status="open" # Will go to in_progress on first scan
    )
    db.add(new_sess)
    db.flush()

    # Move the item
    item.session_id = new_sess.id
    
    # Move the labels associated with this SKU in the old session
    labels = db.query(Label).filter(
        Label.session_id == old_session.id,
        Label.sku == item.sku
    ).all()
    for lb in labels:
        lb.session_id = new_sess.id

    # Check if the old session is now empty or complete
    db.flush() 
    _auto_complete_session(db, old_session.id)
    
    db.commit()
    return new_sess

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Label, PickingItem
from services.printer import print_labels_for_sku

router = APIRouter()


class PrintRequest(BaseModel):
    session_id: int
    sku: str
    printer_id: int


@router.post("/print")
def print_labels(body: PrintRequest, db: DBSession = Depends(get_db)):
    """Send labels via TCP socket to a network Zebra printer (legacy / fallback)."""
    result = print_labels_for_sku(db, body.session_id, body.sku, body.printer_id)
    if result["status"] == "error":
        raise HTTPException(400, result["message"])
    return result


@router.get("/zpl")
def get_zpl(
    session_id: int = Query(...),
    sku: str = Query(...),
    db: DBSession = Depends(get_db),
):
    """
    Return the raw ZPL blocks stored for a session+SKU, junto com a
    quantidade real de unidades separadas (qty_picked) para que o frontend
    saiba quantas etiquetas deve imprimir no total.

    Lógica de repetição no frontend:
      - Se o arquivo TXT tinha N blocos únicos para o SKU e qty_picked = M:
          → imprimir M vezes ciclando pelos N blocos (M % N)
      - Isso garante impressão correta mesmo quando o parser não extraiu
        todos os blocos do TXT (ex: só 2 de 6 foram vinculados ao SKU).
    """
    labels = (
        db.query(Label)
        .filter(Label.session_id == session_id, Label.sku == sku)
        .order_by(Label.label_index)
        .all()
    )
    if not labels:
        raise HTTPException(404, "Nenhuma etiqueta encontrada para este SKU")

    # Busca a quantidade real separada (para calcular repetições)
    item = (
        db.query(PickingItem)
        .filter(PickingItem.session_id == session_id, PickingItem.sku == sku)
        .first()
    )
    qty_picked = item.qty_picked if item else len(labels)
    qty_required = item.qty_required if item else len(labels)

    return {
        "sku": sku,
        "count": len(labels),
        "qty_picked": qty_picked,
        "qty_required": qty_required,
        "all_printed": all(lb.printed for lb in labels),
        "zpl_blocks": [lb.zpl_content for lb in labels],
    }


class MarkPrintedBody(BaseModel):
    session_id: int
    sku: str


@router.post("/mark-printed")
def mark_printed(body: MarkPrintedBody, db: DBSession = Depends(get_db)):
    """Mark labels as printed: sets labels_printed on PickingItem + legacy Label records."""
    # Marca o PickingItem (novo fluxo ZPL dinâmico)
    item = (
        db.query(PickingItem)
        .filter(PickingItem.session_id == body.session_id, PickingItem.sku == body.sku)
        .first()
    )
    if item:
        item.labels_printed = True

    # Marca Label records se existirem (fluxo legado com TXT)
    labels = (
        db.query(Label)
        .filter(Label.session_id == body.session_id, Label.sku == body.sku)
        .all()
    )
    now = datetime.utcnow()
    for lb in labels:
        lb.printed = True
        lb.printed_at = now

    if not item and not labels:
        raise HTTPException(404, "Item não encontrado")

    db.commit()
    return {"status": "ok", "count": len(labels)}

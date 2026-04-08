"""Send ZPL labels directly to a Zebra printer via raw TCP on port 9100."""
import socket
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from models import Label, Printer


def print_labels_for_sku(db: DBSession, session_id: int, sku: str, printer_id: int) -> dict:
    printer = db.query(Printer).filter(Printer.id == printer_id, Printer.is_active == True).first()
    if not printer:
        return {"status": "error", "message": "Printer not found or inactive"}

    labels = (
        db.query(Label)
        .filter(Label.session_id == session_id, Label.sku == sku)
        .order_by(Label.label_index)
        .all()
    )
    if not labels:
        return {"status": "error", "message": "No labels found for this SKU"}

    sent = 0
    errors = []
    for label in labels:
        try:
            _send_zpl(printer.ip_address, printer.port, label.zpl_content)
            label.printed = True
            label.printed_at = datetime.utcnow()
            sent += 1
        except Exception as e:
            errors.append(str(e))

    db.commit()

    if errors:
        return {"status": "partial", "sent": sent, "errors": errors}
    return {"status": "ok", "sent": sent}


def _send_zpl(ip: str, port: int, zpl: str, timeout: int = 5) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((ip, port))
        s.sendall(zpl.encode("utf-8"))

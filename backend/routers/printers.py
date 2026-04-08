from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Printer

router = APIRouter()


class PrinterCreate(BaseModel):
    name: str
    ip_address: str
    port: int = 9100


@router.get("/")
def list_printers(db: DBSession = Depends(get_db)):
    printers = db.query(Printer).filter(Printer.is_active == True).all()
    return [{"id": p.id, "name": p.name, "ip_address": p.ip_address, "port": p.port} for p in printers]


@router.post("/", status_code=201)
def create_printer(body: PrinterCreate, db: DBSession = Depends(get_db)):
    p = Printer(name=body.name, ip_address=body.ip_address, port=body.port)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "name": p.name, "ip_address": p.ip_address, "port": p.port}


@router.delete("/{printer_id}")
def delete_printer(printer_id: int, db: DBSession = Depends(get_db)):
    p = db.query(Printer).filter(Printer.id == printer_id).first()
    if not p:
        raise HTTPException(404, "Printer not found")
    p.is_active = False
    db.commit()
    return {"status": "ok"}

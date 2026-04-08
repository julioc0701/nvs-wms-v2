from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Operator

router = APIRouter()


class OperatorCreate(BaseModel):
    name: str
    pin_code: str | None = "1234"
    badge: str | None = None

class OperatorLogin(BaseModel):
    operator_id: int
    pin_code: str


@router.get("/")
def list_operators(db: DBSession = Depends(get_db)):
    ops = db.query(Operator).all()
    return [{"id": o.id, "name": o.name, "badge": o.badge, "pin_code": o.pin_code} for o in ops]


@router.post("/", status_code=201)
def create_operator(body: OperatorCreate, db: DBSession = Depends(get_db)):
    op = Operator(name=body.name, badge=body.badge, pin_code=body.pin_code or "1234")
    db.add(op)
    db.commit()
    db.refresh(op)
    return {"id": op.id, "name": op.name, "badge": op.badge}

@router.post("/login", status_code=200)
def login_operator(body: OperatorLogin, db: DBSession = Depends(get_db)):
    op = db.query(Operator).filter(Operator.id == body.operator_id).first()
    if not op:
        raise HTTPException(404, "Operador não encontrado")
    if op.pin_code != body.pin_code:
        raise HTTPException(401, "PIN Incorreto")
    
    return {"status": "ok", "operator": {"id": op.id, "name": op.name, "badge": op.badge}}


@router.get("/badge/{badge}")
def get_by_badge(badge: str, db: DBSession = Depends(get_db)):
    op = db.query(Operator).filter(Operator.badge == badge).first()
    if not op:
        raise HTTPException(404, "Badge not found")
    return {"id": op.id, "name": op.name, "badge": op.badge}

class OperatorPinUpdate(BaseModel):
    pin_code: str

@router.put("/{operator_id}/pin")
def update_operator_pin(operator_id: int, body: OperatorPinUpdate, db: DBSession = Depends(get_db)):
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(404, "Operador não encontrado")
    
    op.pin_code = body.pin_code
    db.commit()
    db.refresh(op)
    return {"status": "ok", "message": "PIN atualizado com sucesso"}

@router.delete("/{operator_id}")
def delete_operator(operator_id: int, db: DBSession = Depends(get_db)):
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(404, "Operador não encontrado")
    
    db.delete(op)
    db.commit()
    return {"status": "ok", "message": "Operador excluído com sucesso"}

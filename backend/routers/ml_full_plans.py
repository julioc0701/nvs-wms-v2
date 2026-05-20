import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import MercadoLivreFullPlan

router = APIRouter()


class FullPlanCreate(BaseModel):
    ml_plan_id: str | None = None
    title: str = Field(default="Planejamento Full ML")
    execution_mode: str = Field(default="manual")
    filter_label: str | None = None
    products_count: int = Field(default=0, ge=0)
    total_units: int = Field(default=0, ge=0)
    created_by: str | None = None
    notes: str | None = None
    raw_payload: dict[str, Any] | None = None


def serialize_plan(plan: MercadoLivreFullPlan) -> dict[str, Any]:
    raw_payload = None
    if plan.raw_payload_json:
        try:
            raw_payload = json.loads(plan.raw_payload_json)
        except Exception:
            raw_payload = None
    return {
        "id": plan.id,
        "ml_plan_id": plan.ml_plan_id,
        "title": plan.title,
        "status": plan.status,
        "execution_mode": plan.execution_mode,
        "filter_label": plan.filter_label,
        "products_count": plan.products_count,
        "total_units": plan.total_units,
        "created_by": plan.created_by,
        "notes": plan.notes,
        "raw_payload": raw_payload,
        "created_at": plan.created_at.isoformat(),
    }


@router.get("")
def list_full_plans(limit: int = 100, db: DBSession = Depends(get_db)):
    limit = max(1, min(limit, 500))
    plans = (
        db.query(MercadoLivreFullPlan)
        .order_by(MercadoLivreFullPlan.created_at.desc())
        .limit(limit)
        .all()
    )
    return [serialize_plan(plan) for plan in plans]


@router.post("", status_code=201)
def create_full_plan(body: FullPlanCreate, db: DBSession = Depends(get_db)):
    mode = body.execution_mode.strip().lower()
    if mode not in {"manual", "assisted", "automatic"}:
        raise HTTPException(400, "execution_mode inválido. Use manual, assisted ou automatic.")

    plan = MercadoLivreFullPlan(
        ml_plan_id=(body.ml_plan_id or "").strip() or None,
        title=(body.title or "Planejamento Full ML").strip(),
        status="created",
        execution_mode=mode,
        filter_label=(body.filter_label or "").strip() or None,
        products_count=body.products_count,
        total_units=body.total_units,
        created_by=(body.created_by or "").strip() or None,
        notes=(body.notes or "").strip() or None,
        raw_payload_json=json.dumps(body.raw_payload, ensure_ascii=False) if body.raw_payload else None,
        created_at=datetime.utcnow(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return serialize_plan(plan)


@router.delete("/{plan_id}", status_code=200)
def delete_full_plan(plan_id: int, db: DBSession = Depends(get_db)):
    plan = db.query(MercadoLivreFullPlan).filter(MercadoLivreFullPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Planejamento não encontrado")
    db.delete(plan)
    db.commit()
    return {"status": "ok", "id": plan_id}

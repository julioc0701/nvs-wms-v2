import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import MercadoLivreFullAgentState, MercadoLivreFullPlan, MercadoLivreFullPlanningTask

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


class FullPlanningTaskCreate(BaseModel):
    run_mode: str = Field(default="simulate")
    units_strategy: str = Field(default="formula")
    fixed_units: int | None = Field(default=None, ge=1)
    percentage: int = Field(default=20, ge=0, le=500)
    min_units: int = Field(default=0, ge=0, le=999999)
    filter_label: str | None = None
    filters: list[str] = Field(default_factory=lambda: [
        "WITHOUT_STOCK",
        "WITH_MEDIUM_STOCK",
        "WITH_CRITICAL_STOCK",
        "WITH_ENOUGH_STOCK",
        "WITH_LOW_STOCK",
    ])
    requested_by: str | None = None
    agent_id: str | None = Field(default="mac-local-julio")


class AgentHeartbeat(BaseModel):
    agent_id: str = Field(default="mac-local-julio")
    status: str = Field(default="online")
    message: str | None = None


class TaskComplete(BaseModel):
    status: str = Field(default="created")
    ml_plan_id: str | None = None
    products_count: int = Field(default=0, ge=0)
    total_units: int = Field(default=0, ge=0)
    notes: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None


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


def serialize_task(task: MercadoLivreFullPlanningTask) -> dict[str, Any]:
    def loads(value: str | None):
        if not value:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    return {
        "id": task.id,
        "status": task.status,
        "requested_by": task.requested_by,
        "agent_id": task.agent_id,
        "run_mode": task.run_mode,
        "units_strategy": task.units_strategy,
        "fixed_units": task.fixed_units,
        "percentage": task.percentage,
        "min_units": task.min_units,
        "filter_label": task.filter_label,
        "filters": loads(task.filters_json) or [],
        "result": loads(task.result_json),
        "error_message": task.error_message,
        "created_plan_id": task.created_plan_id,
        "products_count": task.products_count,
        "total_units": task.total_units,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def get_agent_state(db: DBSession) -> MercadoLivreFullAgentState:
    state = db.query(MercadoLivreFullAgentState).filter(MercadoLivreFullAgentState.id == 1).first()
    if not state:
        state = MercadoLivreFullAgentState(id=1, agent_id="mac-local-julio", status="offline")
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def extract_inbound_ids(result: dict[str, Any] | None) -> list[str]:
    if not result:
        return []
    inbounds = ((result.get("saveResult") or {}).get("inbounds") or [])
    ids: list[str] = []
    for inbound in inbounds:
        inbound_id = str((inbound or {}).get("id") or "").strip()
        if inbound_id and inbound_id not in ids:
            ids.append(inbound_id)
    return ids


def extract_inbounds(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not result:
        return []
    inbounds = ((result.get("saveResult") or {}).get("inbounds") or [])
    return [inbound for inbound in inbounds if str((inbound or {}).get("id") or "").strip()]


def parse_ml_int(value: Any) -> int:
    if value is None:
        return 0
    digits = "".join(char for char in str(value) if char.isdigit())
    return int(digits) if digits else 0


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


@router.get("/automation/status")
def get_automation_status(db: DBSession = Depends(get_db)):
    state = get_agent_state(db)
    pending_count = db.query(MercadoLivreFullPlanningTask).filter(
        MercadoLivreFullPlanningTask.status == "pending"
    ).count()
    running = db.query(MercadoLivreFullPlanningTask).filter(
        MercadoLivreFullPlanningTask.status == "running"
    ).first()
    is_online = bool(state.last_seen_at and state.last_seen_at > datetime.utcnow() - timedelta(minutes=2))
    return {
        "agent": {
            "agent_id": state.agent_id,
            "status": "online" if is_online else "offline",
            "last_seen_at": state.last_seen_at.isoformat() if state.last_seen_at else None,
            "last_message": state.last_message,
        },
        "pending_count": pending_count,
        "running_task": serialize_task(running) if running else None,
    }


@router.get("/automation/tasks")
def list_tasks(limit: int = 20, db: DBSession = Depends(get_db)):
    limit = max(1, min(limit, 100))
    tasks = (
        db.query(MercadoLivreFullPlanningTask)
        .order_by(MercadoLivreFullPlanningTask.created_at.desc())
        .limit(limit)
        .all()
    )
    return [serialize_task(task) for task in tasks]


@router.post("/automation/tasks", status_code=201)
def create_task(body: FullPlanningTaskCreate, db: DBSession = Depends(get_db)):
    run_mode = body.run_mode.strip().lower()
    if run_mode not in {"simulate", "save"}:
        raise HTTPException(400, "run_mode inválido. Use simulate ou save.")

    units_strategy = body.units_strategy.strip().lower()
    if units_strategy not in {"formula", "fixed"}:
        raise HTTPException(400, "units_strategy inválido. Use formula ou fixed.")
    if units_strategy == "fixed" and not body.fixed_units:
        raise HTTPException(400, "fixed_units é obrigatório para estratégia fixed.")

    task = MercadoLivreFullPlanningTask(
        status="pending",
        requested_by=(body.requested_by or "").strip() or None,
        agent_id=(body.agent_id or "mac-local-julio").strip(),
        run_mode=run_mode,
        units_strategy=units_strategy,
        fixed_units=body.fixed_units,
        percentage=body.percentage,
        min_units=body.min_units,
        filter_label=(body.filter_label or "").strip() or None,
        filters_json=json.dumps(body.filters, ensure_ascii=False),
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@router.post("/agent/heartbeat")
def agent_heartbeat(body: AgentHeartbeat, db: DBSession = Depends(get_db)):
    state = get_agent_state(db)
    state.agent_id = (body.agent_id or "mac-local-julio").strip()
    state.status = (body.status or "online").strip().lower()
    state.last_message = (body.message or "").strip() or None
    state.last_seen_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "agent": state.agent_id}


@router.get("/agent/next-task")
def get_next_task(agent_id: str = "mac-local-julio", db: DBSession = Depends(get_db)):
    state = get_agent_state(db)
    state.agent_id = agent_id
    state.status = "online"
    state.last_seen_at = datetime.utcnow()
    state.last_message = "consultando tarefas"

    task = (
        db.query(MercadoLivreFullPlanningTask)
        .filter(MercadoLivreFullPlanningTask.status == "pending")
        .filter(MercadoLivreFullPlanningTask.agent_id.in_([agent_id, None]))
        .order_by(MercadoLivreFullPlanningTask.created_at.asc())
        .first()
    )
    if task:
        task.status = "running"
        task.agent_id = agent_id
        task.started_at = datetime.utcnow()
    db.commit()
    if task:
        db.refresh(task)
    return serialize_task(task) if task else {"task": None}


@router.post("/agent/tasks/{task_id}/complete")
def complete_task(task_id: int, body: TaskComplete, db: DBSession = Depends(get_db)):
    task = db.query(MercadoLivreFullPlanningTask).filter(MercadoLivreFullPlanningTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Tarefa não encontrada")

    status = body.status.strip().lower()
    if status not in {"created", "simulated", "failed", "needs_login"}:
        raise HTTPException(400, "status inválido.")

    task.status = status
    task.finished_at = datetime.utcnow()
    task.error_message = (body.error_message or "").strip() or None
    task.created_plan_id = (body.ml_plan_id or "").strip() or None
    task.products_count = body.products_count
    task.total_units = body.total_units
    task.result_json = json.dumps(body.result, ensure_ascii=False) if body.result else None

    if status == "created" and body.ml_plan_id:
        inbounds = extract_inbounds(body.result)
        if inbounds:
            for inbound in inbounds:
                inbound_id = str(inbound.get("id") or "").strip()
                units = parse_ml_int(inbound.get("unitsText"))
                products = parse_ml_int(inbound.get("productsText"))
                group = str(inbound.get("group") or "").strip()
                notes = (
                    f"Plano pai ML: {body.ml_plan_id}. "
                    f"Envio gerado pelo agente local."
                    f"{f' Grupo: {group}.' if group else ''}"
                )
                plan = MercadoLivreFullPlan(
                    ml_plan_id=inbound_id,
                    title=f"Envio Full ML #{inbound_id}",
                    status="created",
                    execution_mode="automatic",
                    filter_label=task.filter_label,
                    products_count=products,
                    total_units=units,
                    created_by=task.requested_by,
                    notes=notes,
                    raw_payload_json=json.dumps({
                        "parent_ml_plan_id": body.ml_plan_id,
                        "inbound": inbound,
                        "task_result": body.result,
                    }, ensure_ascii=False),
                    created_at=datetime.utcnow(),
                )
                db.add(plan)
        else:
            inbound_ids = extract_inbound_ids(body.result)
            notes_parts = []
            if body.notes:
                notes_parts.append(body.notes.strip())
            if inbound_ids:
                notes_parts.append(f"Envios ML: {', '.join(inbound_ids)}.")
            plan = MercadoLivreFullPlan(
                ml_plan_id=body.ml_plan_id,
                title=f"Agente Full ML - envios {', '.join(inbound_ids)}" if inbound_ids else "Agente Full ML",
                status="created",
                execution_mode="automatic",
                filter_label=task.filter_label,
                products_count=body.products_count,
                total_units=body.total_units,
                created_by=task.requested_by,
                notes=" ".join(notes_parts).strip() or None,
                raw_payload_json=json.dumps(body.result, ensure_ascii=False) if body.result else None,
                created_at=datetime.utcnow(),
            )
            db.add(plan)

    state = get_agent_state(db)
    state.status = "online" if status in {"created", "simulated"} else status
    state.last_seen_at = datetime.utcnow()
    state.last_message = f"tarefa {task_id}: {status}"
    db.commit()
    db.refresh(task)
    return serialize_task(task)

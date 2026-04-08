"""
Fila de impressão — print_jobs
================================
GET  /print-jobs/pending          → agente local: busca jobs PENDING
PATCH /print-jobs/{id}            → agente local: atualiza status
GET  /print-jobs?session_id=&sku= → frontend: consulta status do job atual
POST /print-jobs                  → frontend: cria job com ZPL gerado
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import PrintJob, PickingItem

router = APIRouter()


# ---------------------------------------------------------------------------
# Agente: busca jobs pendentes
# ---------------------------------------------------------------------------

@router.get("/pending")
def get_pending_jobs(db: DBSession = Depends(get_db)):
    from datetime import timedelta

    # Crash recovery: se ficou PRINTING por mais de 5 min, volta para PENDING
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    stale = (
        db.query(PrintJob)
        .filter(PrintJob.status == "PRINTING", PrintJob.created_at < cutoff)
        .all()
    )
    for job in stale:
        job.status = "PENDING"
        job.error_msg = "Resetado por timeout (agente caiu?)"
    if stale:
        db.commit()

    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.status == "PENDING")
        .order_by(PrintJob.created_at)
        .all()
    )
    return [_job_dict(j) for j in jobs]


# ---------------------------------------------------------------------------
# Agente: atualiza status do job
# ---------------------------------------------------------------------------

class UpdateJobBody(BaseModel):
    status: str
    printer_name: str | None = None
    error_msg: str | None = None


@router.patch("/{job_id}")
def update_job(job_id: int, body: UpdateJobBody, db: DBSession = Depends(get_db)):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job não encontrado")

    valid = {"PRINTING", "PRINTED", "ERROR"}
    if body.status not in valid:
        raise HTTPException(400, f"Status inválido. Use: {valid}")

    job.status = body.status
    if body.printer_name:
        job.printer_name = body.printer_name
    if body.error_msg:
        job.error_msg = body.error_msg

    if body.status == "PRINTED":
        job.printed_at = datetime.utcnow()
        # Marca o PickingItem como impresso
        item = db.query(PickingItem).filter(
            PickingItem.session_id == job.session_id,
            PickingItem.sku == job.sku,
        ).first()
        if item:
            item.labels_printed = True

    db.commit()
    return _job_dict(job)


# ---------------------------------------------------------------------------
# Frontend: consulta status do job mais recente para session+sku
# ---------------------------------------------------------------------------

@router.get("")
def get_job_status(
    session_id: int = Query(...),
    sku: str = Query(...),
    db: DBSession = Depends(get_db),
):
    job = (
        db.query(PrintJob)
        .filter(PrintJob.session_id == session_id, PrintJob.sku == sku)
        .order_by(PrintJob.id.desc())
        .first()
    )
    if not job:
        return None
    return _job_dict(job)


# ---------------------------------------------------------------------------
# Frontend: cria job com ZPL gerado dinamicamente
# ---------------------------------------------------------------------------

class CreateJobBody(BaseModel):
    session_id: int
    sku: str
    zpl_content: str
    operator_id: int | None = None


@router.post("")
def create_job(body: CreateJobBody, db: DBSession = Depends(get_db)):
    if not body.zpl_content.strip():
        raise HTTPException(400, "ZPL vazio")

    # Cancela jobs anteriores com erro para permitir retry
    db.query(PrintJob).filter(
        PrintJob.session_id == body.session_id,
        PrintJob.sku == body.sku,
        PrintJob.status == "ERROR",
    ).delete()

    # Bloqueia duplicata em andamento
    active = (
        db.query(PrintJob)
        .filter(
            PrintJob.session_id == body.session_id,
            PrintJob.sku == body.sku,
            PrintJob.status.in_(["PENDING", "PRINTING"]),
        )
        .first()
    )
    if active:
        return _job_dict(active)

    job = PrintJob(
        session_id=body.session_id,
        sku=body.sku,
        zpl_content=body.zpl_content,
        operator_id=body.operator_id,
        status="PENDING",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_dict(job)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _job_dict(job: PrintJob) -> dict:
    return {
        "id": job.id,
        "session_id": job.session_id,
        "sku": job.sku,
        "status": job.status,
        "zpl_content": job.zpl_content,
        "printer_name": job.printer_name,
        "error_msg": job.error_msg,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "printed_at": job.printed_at.isoformat() if job.printed_at else None,
    }

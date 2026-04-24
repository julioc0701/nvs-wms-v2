"""
Fila de impressao - print_jobs
"""

import hashlib
import re
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import PickingItem, PrintJob

router = APIRouter()


@router.get("/pending")
def get_pending_jobs(db: DBSession = Depends(get_db)):
    # Crash recovery conservador: so recicla jobs travados ha bastante tempo.
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    stale = (
        db.query(PrintJob)
        .filter(PrintJob.status == "PRINTING")
        .all()
    )
    changed = False
    for job in stale:
        ref = job.started_at or job.claimed_at or job.created_at
        if ref and ref < cutoff:
            job.status = "PENDING"
            job.claimed_by = None
            job.claimed_at = None
            job.started_at = None
            job.job_token = None
            job.error_msg = "Resetado por timeout de impressao"
            changed = True
    if changed:
        db.commit()

    jobs = (
        db.query(PrintJob)
        .filter(PrintJob.status == "PENDING")
        .order_by(PrintJob.created_at)
        .all()
    )
    return [_job_dict(j) for j in jobs]


class UpdateJobBody(BaseModel):
    status: str
    printer_name: str | None = None
    error_msg: str | None = None


@router.patch("/{job_id}")
def update_job(job_id: int, body: UpdateJobBody, db: DBSession = Depends(get_db)):
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job nao encontrado")

    valid = {"PRINTING", "PRINTED", "ERROR"}
    if body.status not in valid:
        raise HTTPException(400, f"Status invalido. Use: {valid}")

    job.status = body.status
    if body.printer_name:
        job.printer_name = body.printer_name
    if body.error_msg:
        job.error_msg = body.error_msg

    if body.status == "PRINTING" and not job.started_at:
        job.started_at = datetime.utcnow()

    if body.status == "PRINTED":
        job.printed_at = datetime.utcnow()
        job.error_msg = None
        item = db.query(PickingItem).filter(
            PickingItem.session_id == job.session_id,
            PickingItem.sku == job.sku,
        ).first()
        if item:
            item.labels_printed = True

    db.commit()
    return _job_dict(job)


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


class CreateJobBody(BaseModel):
    session_id: int
    sku: str
    zpl_content: str
    operator_id: int | None = None
    machine_id: str | None = None


@router.post("")
async def create_job(body: CreateJobBody, db: DBSession = Depends(get_db)):
    if not body.zpl_content.strip():
        raise HTTPException(400, "ZPL vazio")

    from services.zebra_connection import zebra_manager

    db.query(PrintJob).filter(
        PrintJob.session_id == body.session_id,
        PrintJob.sku == body.sku,
        PrintJob.status == "ERROR",
    ).delete()

    pending = (
        db.query(PrintJob)
        .filter(
            PrintJob.session_id == body.session_id,
            PrintJob.sku == body.sku,
            PrintJob.status == "PENDING",
        )
        .first()
    )
    if pending:
        _prepare_for_push(pending, body.zpl_content)
        db.commit()

        claimed_by = await zebra_manager.push_job(_push_payload(pending), machine_id=body.machine_id)
        if claimed_by:
            pending.status = "PRINTING"
            pending.claimed_by = claimed_by
            pending.claimed_at = datetime.utcnow()
            pending.started_at = pending.claimed_at
            db.commit()
            db.refresh(pending)
        return _job_dict(pending)

    active = (
        db.query(PrintJob)
        .filter(
            PrintJob.session_id == body.session_id,
            PrintJob.sku == body.sku,
            PrintJob.status == "PRINTING",
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
    _prepare_for_push(job, body.zpl_content)
    db.add(job)
    db.commit()
    db.refresh(job)

    claimed_by = await zebra_manager.push_job(_push_payload(job), machine_id=body.machine_id)
    if claimed_by:
        job.status = "PRINTING"
        job.claimed_by = claimed_by
        job.claimed_at = datetime.utcnow()
        job.started_at = job.claimed_at
        db.commit()
        db.refresh(job)

    return _job_dict(job)


def _zpl_hash(zpl_content: str) -> str:
    return hashlib.sha256(zpl_content.encode("utf-8")).hexdigest()


def _zpl_block_count(zpl_content: str) -> int:
    blocks = re.findall(r"\^XA.*?\^XZ", zpl_content, flags=re.DOTALL | re.IGNORECASE)
    return len(blocks) if blocks else (1 if zpl_content.strip() else 0)


def _prepare_for_push(job: PrintJob, zpl_content: str) -> None:
    job.zpl_content = zpl_content
    job.job_token = uuid4().hex
    job.zpl_hash = _zpl_hash(zpl_content)
    job.zpl_block_count = _zpl_block_count(zpl_content)
    job.error_msg = None
    job.claimed_by = None
    job.claimed_at = None
    job.started_at = None


def _push_payload(job: PrintJob) -> dict:
    return {
        "id": job.id,
        "sku": job.sku,
        "zpl_content": job.zpl_content,
        "job_token": job.job_token,
        "zpl_hash": job.zpl_hash,
        "zpl_block_count": job.zpl_block_count,
    }


def _job_dict(job: PrintJob) -> dict:
    return {
        "id": job.id,
        "session_id": job.session_id,
        "sku": job.sku,
        "status": job.status,
        "zpl_content": job.zpl_content,
        "printer_name": job.printer_name,
        "error_msg": job.error_msg,
        "claimed_by": job.claimed_by,
        "claimed_at": job.claimed_at.isoformat() if job.claimed_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "agent_version": job.agent_version,
        "zpl_hash": job.zpl_hash,
        "zpl_block_count": job.zpl_block_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "printed_at": job.printed_at.isoformat() if job.printed_at else None,
    }

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func
from database import get_db
from models import ScanEvent, Operator, Session, Batch

router = APIRouter()


@router.get("/ranking")
def get_operator_ranking(
    db: DBSession = Depends(get_db),
    batch_id: int | None = Query(default=None, description="Filter by batch. Omit for all-time Geral ranking."),
    marketplace: str | None = Query(default=None, description="Filter Geral ranking by marketplace (ml or shopee)."),
):
    """
    Returns a ranking of operators by total quantity picked.

    - batch_id=None  → All-time 'Geral' ranking (every scan ever recorded, all batches)
    - batch_id=N     → Ranking filtered to scans made on sessions belonging to batch N
    """
    q = (
        db.query(
            Operator.name,
            func.sum(ScanEvent.qty_delta).label("total_picked")
        )
        .join(ScanEvent, ScanEvent.operator_id == Operator.id)
        .filter(ScanEvent.event_type.in_(["scan", "scan_box", "undo", "shortage"]))
    )

    if batch_id:
        # Filter by session → batch relationship
        batch_session_ids = (
            db.query(Session.id)
            .filter(Session.batch_id == batch_id)
            .subquery()
        )
        q = q.filter(ScanEvent.session_id.in_(batch_session_ids))
    elif marketplace:
        # Filter all-time ranking by marketplace
        marketplace_session_ids = (
            db.query(Session.id)
            .filter(Session.marketplace == marketplace)
            .subquery()
        )
        q = q.filter(ScanEvent.session_id.in_(marketplace_session_ids))

    results = (
        q.group_by(Operator.name)
        .order_by(func.sum(ScanEvent.qty_delta).desc())
        .limit(20)
        .all()
    )

    return [
        {"name": r.name, "total": int(r.total_picked or 0)}
        for r in results
        if (r.total_picked or 0) > 0
    ]


@router.get("/batches-for-ranking")
def get_batches_for_ranking(db: DBSession = Depends(get_db)):
    """Return list of batches to populate the ranking selector (active + archived)."""
    batches = (
        db.query(Batch.id, Batch.name, Batch.status, Batch.full_date, Batch.marketplace)
        .order_by(Batch.full_date.desc(), Batch.seq.desc())
        .all()
    )
    return [
        {"id": b.id, "name": b.name, "status": b.status, "marketplace": b.marketplace}
        for b in batches
    ]

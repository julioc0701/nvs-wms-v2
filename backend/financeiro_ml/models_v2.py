"""Schema v2 multi-seller do financeiro ML. Liga em FinBase (db isolada)."""
from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Text, DateTime, Date, Numeric, Index, PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from financeiro_ml.db import FinBase

# Safe for reload: clear stale table registrations on current FinBase metadata
for _tname in list(FinBase.metadata.tables.keys()):
    FinBase.metadata.remove(FinBase.metadata.tables[_tname])


class MLTokens(FinBase):
    __tablename__ = "ml_tokens"
    seller_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # = user_id ML
    client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    refresh_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkuFinanceiro(FinBase):
    __tablename__ = "sku_financeiro"
    sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    custo_unit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    imposto_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=False)


class MLOrderCache(FinBase):
    __tablename__ = "ml_orders_cache"
    __table_args__ = (
        PrimaryKeyConstraint("seller_id", "order_id"),
        Index("ix_orders_ref", "seller_id", "date_closed", "date_created"),
        Index("ix_orders_dlu", "seller_id", "date_last_updated"),
        Index("ix_orders_ship", "seller_id", "shipment_id"),
    )
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date_created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date_closed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    status_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    produto_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    frete_comprador: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    frete_vendedor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_bruta: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_refund: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    refund_amount_partial: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    cupom_seller: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    modalidade_anuncio: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logistic_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breakdown_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    frete_incerto: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # bug 4: marca incerteza
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MLOrderItemCache(FinBase):
    __tablename__ = "ml_order_items_cache"
    __table_args__ = (
        UniqueConstraint("seller_id", "order_id", "item_id", name="uq_ml_item_seller_order_item"),
        Index("ix_items_order", "seller_id", "order_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(30), nullable=True)


class MLDaySyncStatus(FinBase):
    __tablename__ = "ml_day_sync_status"
    __table_args__ = (PrimaryKeyConstraint("seller_id", "day"),)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok|failed|rate_limited|partial|imported_unverified
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MLBackfillJob(FinBase):
    __tablename__ = "ml_backfill_jobs"
    __table_args__ = (Index("ix_jobs_status", "status", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day_from: Mapped[date] = mapped_column(Date, nullable=False)
    day_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|running|done|failed|cancelled
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MLCanaryRun(FinBase):
    __tablename__ = "ml_canary_runs"
    __table_args__ = (Index("ix_canary_runs_seller_day", "seller_id", "day", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_shipments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_discounts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_shipping_costs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MLCanaryOrderSnapshot(FinBase):
    __tablename__ = "ml_canary_order_snapshots"
    __table_args__ = (
        UniqueConstraint("run_id", "order_id", name="uq_canary_snapshot_run_order"),
        Index("ix_canary_snapshot_run", "run_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ingest_status: Mapped[str] = mapped_column(String(40), nullable=False)
    missing_flags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class MLCanaryPendingTask(FinBase):
    __tablename__ = "ml_canary_pending_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "ref_id", name="uq_canary_task_run_kind_ref"),
        Index("ix_canary_tasks_status", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class MLSellerLock(FinBase):
    __tablename__ = "ml_seller_lock"
    seller_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holder: Mapped[str | None] = mapped_column(String(60), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

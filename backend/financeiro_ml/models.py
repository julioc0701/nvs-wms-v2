from datetime import datetime, date
from sqlalchemy import Integer, String, Text, DateTime, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


# ============================================================
# Financeiro ML — Mercado Livre (Resumo Financeiro)
# ============================================================

class MLTokens(Base):
    __tablename__ = "ml_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkuFinanceiro(Base):
    __tablename__ = "sku_financeiro"

    sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    custo_unit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    imposto_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)


class MLOrderCache(Base):
    __tablename__ = "ml_orders_cache"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_created: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    date_closed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
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
    breakdown_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    synced_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MLOrderItemCache(Base):
    __tablename__ = "ml_order_items_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("ml_orders_cache.order_id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(30), nullable=True)


class MLDaySyncStatus(Base):
    __tablename__ = "ml_day_sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

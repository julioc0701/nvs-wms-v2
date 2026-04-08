from datetime import datetime, date
from sqlalchemy import Integer, String, Text, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Batch(Base):
    """Agrupa sessões de picking por data de carregamento do Full."""
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_date: Mapped[date] = mapped_column(Date, nullable=False)   # data do carregamento
    seq: Mapped[int] = mapped_column(Integer, default=1)            # 1, 2... se mesma data
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "19/03/2026"
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | archived
    marketplace: Mapped[str] = mapped_column(String(20), default="ml") # ml | shopee
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["Session"]] = relationship(back_populates="batch")


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    pin_code: Mapped[str] = mapped_column(String(20), nullable=False, default="1234")
    badge: Mapped[str | None] = mapped_column(String(100), unique=True)
    sessions: Mapped[list["Session"]] = relationship(back_populates="operator")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"))  # NOVO
    status: Mapped[str] = mapped_column(String(20), default="open")
    # open | in_progress | completed
    marketplace: Mapped[str] = mapped_column(String(20), default="ml") # ml | shopee
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    operator: Mapped["Operator | None"] = relationship(back_populates="sessions")
    batch: Mapped["Batch | None"] = relationship(back_populates="sessions")  # NOVO
    items: Mapped[list["PickingItem"]] = relationship(back_populates="session", order_by="PickingItem.id")
    labels: Mapped[list["Label"]] = relationship(back_populates="session")


class PickingItem(Base):
    __tablename__ = "picking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    ml_code: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    qty_required: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_picked: Mapped[int] = mapped_column(Integer, default=0)
    shortage_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | in_progress | complete | partial | out_of_stock
    labels_printed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="items")
    scan_events: Mapped[list["ScanEvent"]] = relationship(back_populates="item")


class Barcode(Base):
    __tablename__ = "barcodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    barcode: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    label_index: Mapped[int] = mapped_column(Integer, nullable=False)
    zpl_content: Mapped[str] = mapped_column(Text, nullable=False)
    printed: Mapped[bool] = mapped_column(Boolean, default=False)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime)

    session: Mapped["Session"] = relationship(back_populates="labels")


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    picking_item_id: Mapped[int] = mapped_column(ForeignKey("picking_items.id"), nullable=False)
    barcode: Mapped[str] = mapped_column(String(200), nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # scan | undo | shortage | out_of_stock | substitution | reopen
    qty_delta: Mapped[int] = mapped_column(Integer, default=1)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped["PickingItem"] = relationship(back_populates="scan_events")


class Printer(Base):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=9100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PrintJob(Base):
    """Fila persistente de impressão — criada ao finalizar bipagem de um item."""
    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    zpl_content: Mapped[str] = mapped_column(Text, nullable=False)
    # PENDING → PRINTING → PRINTED | ERROR
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    printer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

from datetime import datetime, date
from sqlalchemy import Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Float
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
    claimed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    job_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zpl_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zpl_block_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TinyOrderSync(Base):
    """Tabela de Espelho Local para armazenar dados pesados do Tiny ERP (Marcadores, Ecommerce)"""
    __tablename__ = "tiny_orders_sync"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # O id do pedido no Tiny
    numero: Mapped[str] = mapped_column(String(50), nullable=True)
    ecommerce: Mapped[str | None] = mapped_column(String(100), nullable=True)
    marcadores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    deposito: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["TinyOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class TinyOrderItem(Base):
    """Tabela de Itens de cada Pedido Sincronizado do Tiny ERP para Análises Isoladas (Ex: Gemma 4)"""
    __tablename__ = "tiny_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tiny_order_id: Mapped[str] = mapped_column(ForeignKey("tiny_orders_sync.id"), nullable=False)
    id_produto: Mapped[str | None] = mapped_column(String(50), nullable=True)
    codigo: Mapped[str | None] = mapped_column(String(100), nullable=True)  # SKU do ERP
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_unitario: Mapped[float | None] = mapped_column(Float, nullable=True)

    order: Mapped["TinyOrderSync"] = relationship(back_populates="items")


class AgentMemory(Base):
    """
    Tabela de Memória de Agentes (MAS).
    Armazena o histórico do loop de conversas, separando por perfis e retendo o raciocínio.
    """
    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False) # Identifica a "thread" aberta pelo usuário
    agent_role: Mapped[str] = mapped_column(String(50), nullable=False)  # orquestrador, data_scientist, etc.
    message_type: Mapped[str] = mapped_column(String(20), nullable=False) # system, user, assistant, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True) # Se foi retorno de tool
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    """
    Trilhas resumidas de execução do ecossistema de agentes.
    Serve para observabilidade, auditoria e depuração de falhas.
    """
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    orchestrator_role: Mapped[str] = mapped_column(String(50), nullable=False, default="orquestrador")
    specialist_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_args_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OrderOperational(Base):
    """
    Camada canônica para consultas operacionais rápidas.
    Uma linha por pedido com status e datas já normalizados.
    """
    __tablename__ = "orders_operational"

    order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    numero: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    order_date: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)  # YYYY-MM-DD
    invoice_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    shipping_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    delivery_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status_bucket: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_operational_sale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    total_value: Mapped[float] = mapped_column(Float, default=0.0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    source_name: Mapped[str] = mapped_column(String(30), default="tiny_api")
    last_source_update_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SyncRun(Base):
    """
    Auditoria das execuções de sync para carga inicial, incremental e reconciliação.
    """
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    window_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    window_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    orders_seen: Mapped[int] = mapped_column(Integer, default=0)
    orders_inserted: Mapped[int] = mapped_column(Integer, default=0)
    orders_updated: Mapped[int] = mapped_column(Integer, default=0)
    orders_failed: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TinyPickingList(Base):
    """Lista de Separação Mestre criada a partir de múltiplos pedidos do Tiny."""
    __tablename__ = "tiny_picking_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente") # pendente, em_andamento, concluida
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["TinyPickingListItem"]] = relationship(back_populates="list", cascade="all, delete-orphan")


class TinyPickingListItem(Base):
    """Itens consolidados de uma lista de separação do Tiny, agrupados por SKU."""
    __tablename__ = "tiny_picking_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("tiny_picking_lists.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    qty_picked: Mapped[float] = mapped_column(Float, default=0.0) 
    qty_shortage: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(100), index=True)
    source_separation_ids: Mapped[str | None] = mapped_column(Text)
    picked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) # Controle de coleta
    is_shortage: Mapped[bool] = mapped_column(Boolean, default=False)

    list: Mapped["TinyPickingList"] = relationship(back_populates="items")


class TinySeparationItemCache(Base):
    """Cache local de itens de separação do Tiny.
    Aquecido em background quando a tela carrega — elimina as N chamadas ao Tiny
    na hora de gerar a lista. TTL de 6h, apagado após virar lista."""
    __tablename__ = "tiny_separation_item_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    separation_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[str | None] = mapped_column(String(100))
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TinySeparationStatus(Base):
    """Espelho local do status de documentos de separação do Tiny.
    O Tiny é somente-leitura — nunca escrevemos de volta.
    Esta tabela registra localmente quando um documento foi incluído em uma lista de separação."""
    __tablename__ = "tiny_separation_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    separation_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, unique=True)
    status: Mapped[str] = mapped_column(String(30), default="em_separacao")  # em_separacao | concluida
    list_id: Mapped[int | None] = mapped_column(ForeignKey("tiny_picking_lists.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TinySeparationHeader(Base):
    """Cache local dos campos de exibição de documentos de separação do Tiny.
    Populado/atualizado toda vez que /separacoes é chamado.
    Permite que as abas 'em separação' e 'separadas' sirvam dados do DB local
    sem depender de filtros de data da API do Tiny."""
    __tablename__ = "tiny_separation_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    separation_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, unique=True)
    numero: Mapped[str | None] = mapped_column(String(50))
    destinatario: Mapped[str | None] = mapped_column(String(255))
    numero_ec: Mapped[str | None] = mapped_column(String(100))          # numeroPedidoEcommerce
    data_emissao: Mapped[str | None] = mapped_column(String(30))
    prazo_maximo: Mapped[str | None] = mapped_column(String(30))
    id_forma_envio: Mapped[str | None] = mapped_column(String(50))
    forma_envio_descricao: Mapped[str | None] = mapped_column(String(100))
    numero_pedido: Mapped[str | None] = mapped_column(String(50))       # injetado pelo espelho local
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TinyErpSendLog(Base):
    """Log de envios para o ERP Tiny via separacao.alterar.situacao.php.
    Registra cada tentativa (manual ou automática) com o resultado completo."""
    __tablename__ = "tiny_erp_send_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    separation_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)  # manual | auto
    status: Mapped[str] = mapped_column(String(20), nullable=False)        # success | error
    response_json: Mapped[str | None] = mapped_column(Text)                # resposta bruta do Tiny
    error_message: Mapped[str | None] = mapped_column(Text)                # mensagem de erro legível
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Shortage(Base):
    """Relatório de faltas/estoque zerado."""
    __tablename__ = "shortages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    category: Mapped[str] = mapped_column(String(50), default="organico") # full | organico
    list_id: Mapped[str | None] = mapped_column(String(100), nullable=True) # ID da lista ou sessão
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True) # NOVO
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="pendente")  # pendente | concluido

    operator: Mapped["Operator | None"] = relationship()

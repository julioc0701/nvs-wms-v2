import asyncio
import logging
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Session, PickingItem, Label, Barcode, Operator, ScanEvent, Batch, PrintJob, Shortage
from parsers.ml_pdf_parser import parse_picking_pdf
from parsers.ml_zpl_parser import parse_zpl_file, get_ml_barcodes
from services import picking as svc

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Split helper ─────────────────────────────────────────────────────────────

def split_into_batches(items: list[dict], max_units: int = 1000) -> list[list[dict]]:
    """
    Sort items by qty desc, then greedily fill batches up to max_units.
    Items that alone exceed max_units get their own batch.
    """
    sorted_items = sorted(items, key=lambda x: x["qty_required"], reverse=True)
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_total = 0

    for item in sorted_items:
        qty = item["qty_required"]
        if not current or current_total + qty <= max_units:
            current.append(item)
            current_total += qty
        else:
            batches.append(current)
            current = [item]
            current_total = qty

    if current:
        batches.append(current)

    return batches


# ── Upload ───────────────────────────────────────────────────────────────────

MAX_ACTIVE_BATCHES = 10


def _date_to_prefix(d: date) -> str:
    """Convert a date to a session code prefix. e.g. 2026-03-19 -> '19-03-2026'"""
    return d.strftime("%d-%m-%Y")


def _archive_batch(batch: Batch, db: DBSession):
    """Set batch status to archived (sessions and data are preserved)."""
    batch.status = "archived"
    db.commit()


@router.get("/batches")
def list_batches(db: DBSession = Depends(get_db)):
    """Return all batches with per-batch progress summary and lifecycle.

    Lifecycle (controle manual com 1 auto-transição):
      - 'pendente': criado, nada bipado ainda
      - 'em_andamento': auto-atribuído no 1º bip/falta de qualquer sessão do lote
      - 'finalizado': MANUAL (master clica pra fechar a operação)
      - 'archived': lote arquivado (override de tudo)
    """
    batches = db.query(Batch).order_by(Batch.full_date.asc(), Batch.seq.asc()).all()
    result = []
    for b in batches:
        sess_data = []
        for s in b.sessions:
            s_total  = sum(i.qty_required for i in s.items)
            s_picked = sum(i.qty_picked   for i in s.items)
            s_unique_skus = len({i.sku for i in s.items})
            sess_data.append({
                "id": s.id,
                "session_code": s.session_code,
                "operator_name": s.operator.name if s.operator else None,
                "status": s.status,
                "items_total": s_total,
                "items_picked": s_picked,
                "unique_sku_count": s_unique_skus,
            })
        total_items  = sum(sd["items_total"]  for sd in sess_data)
        total_picked = sum(sd["items_picked"] for sd in sess_data)
        pct = round((total_picked / total_items) * 100) if total_items else 0
        # Phase: archived sobrepõe lifecycle; senão usa lifecycle real do DB
        phase = "archived" if b.status == "archived" else b.lifecycle
        result.append({
            "id": b.id,
            "name": b.name,
            "full_date": b.full_date.isoformat(),
            "seq": b.seq,
            "status": b.status,
            "lifecycle": b.lifecycle,
            "phase": phase,
            "marketplace": b.marketplace,
            "created_at": b.created_at.isoformat(),
            "total_items": total_items,
            "total_picked": total_picked,
            "pct": pct,
            "sessions": sess_data,
        })
    return result


class LifecycleBody(BaseModel):
    lifecycle: str  # em_andamento | finalizado


@router.patch("/batches/{batch_id}/lifecycle")
def set_batch_lifecycle(batch_id: int, body: LifecycleBody, db: DBSession = Depends(get_db)):
    """Altera manualmente o lifecycle do lote. Valores permitidos: 'em_andamento' | 'finalizado'.
    'pendente' nunca é manual (só estado inicial). 'archived' usa endpoint próprio."""
    if body.lifecycle not in ("em_andamento", "finalizado"):
        raise HTTPException(400, "Valor inválido. Use 'em_andamento' ou 'finalizado'.")
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado")
    if batch.status == "archived":
        raise HTTPException(409, "Lote arquivado — desarquive antes de alterar lifecycle.")
    batch.lifecycle = body.lifecycle
    db.commit()
    logger.info("BATCH_LIFECYCLE batch_id=%s lifecycle=%s", batch_id, body.lifecycle)
    return {"status": "ok", "batch_id": batch_id, "lifecycle": batch.lifecycle}


@router.delete("/batches/{batch_id}", status_code=200)
def delete_batch(batch_id: int, db: DBSession = Depends(get_db)):
    """Delete a batch and all its sessions, items and scan events."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado")
    session_ids = [s.id for s in db.query(Session.id).filter(Session.batch_id == batch_id).all()]
    if session_ids:
        item_ids = [i.id for i in db.query(PickingItem.id).filter(PickingItem.session_id.in_(session_ids)).all()]
        if item_ids:
            db.query(ScanEvent).filter(ScanEvent.picking_item_id.in_(item_ids)).delete(synchronize_session=False)
        db.query(PrintJob).filter(PrintJob.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(Label).filter(Label.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(PickingItem).filter(PickingItem.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(Session).filter(Session.id.in_(session_ids)).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()
    return {"status": "ok", "deleted_sessions": len(session_ids)}


@router.post("/batches/{batch_id}/archive")
def archive_batch(batch_id: int, db: DBSession = Depends(get_db)):
    """Manually archive a batch (preserves all sessions and data)."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado")
    if batch.status == "archived":
        return {"ok": True, "msg": "Lote já estava arquivado"}
    _archive_batch(batch, db)
    return {"ok": True, "msg": f"Lote '{batch.name}' arquivado com sucesso"}


@router.post("/upload", status_code=201)
async def upload_session(
    full_date: str = Form(...),           # ISO date: "2026-03-19"
    marketplace: str = Form("ml"),        # ml ou shopee
    picking_pdf: UploadFile = File(...),
    labels_txt: UploadFile | None = File(None),
    force_archive_batch_id: int | None = Form(None),  # confirmed archiving
    db: DBSession = Depends(get_db),
):
    # Parse date
    try:
        batch_date = date.fromisoformat(full_date)
    except ValueError:
        raise HTTPException(400, "Data inválida. Use o formato YYYY-MM-DD.")

    pdf_bytes   = await picking_pdf.read()
    txt_content = (await labels_txt.read()).decode("utf-8", errors="replace") if labels_txt else ""

    logger.info("Upload iniciado: full_date=%s pdf=%d bytes txt=%d bytes",
                full_date, len(pdf_bytes), len(txt_content))

    loop = asyncio.get_event_loop()
    try:
        items_data = []
        labels_data = []

        if marketplace == "shopee":
            from parsers.shopee import parse_picking_pdf as shopee_parse
            from parsers.shopee_zpl_generator import generate_shopee_paired_zpl

            items_data = await asyncio.wait_for(
                loop.run_in_executor(None, shopee_parse, pdf_bytes),
                timeout=120.0,
            )

            for item in items_data:
                qty = int(item.get("qty_required", 1))
                gen_data = {
                    "product_name": item.get("description", ""),
                    "seller_sku": item.get("sku", ""),
                    "barcode": item.get("ml_code", ""),
                    "whs_skuid": item.get("ml_code", "")
                }
                # Gerador em pares (2 unidades por bloco ZPL)
                for idx in range(0, qty, 2):
                    is_single = (idx + 1 == qty)
                    zpl = generate_shopee_paired_zpl(gen_data, is_single=is_single)
                    labels_data.append({
                        "sku": item["sku"],
                        "label_index": (idx // 2) + 1,
                        "zpl_content": zpl
                    })
        else:
            items_data = await asyncio.wait_for(
                loop.run_in_executor(None, parse_picking_pdf, pdf_bytes),
                timeout=120.0,
            )
            if txt_content:
                labels_data = await asyncio.wait_for(
                    loop.run_in_executor(None, parse_zpl_file, txt_content),
                    timeout=60.0,
                )
    except asyncio.TimeoutError:
        logger.error("Timeout ao processar PDF (%d bytes)", len(pdf_bytes))
        raise HTTPException(408, "PDF demorou mais de 2 min. Verifique o arquivo.")
    except Exception as exc:
        logger.exception("Erro ao parsear arquivo")
        raise HTTPException(400, f"Erro ao processar lote: {exc}")

    logger.info("Parse concluído: %d itens, %d etiquetas", len(items_data), len(labels_data))

    if not items_data:
        raise HTTPException(400, f"Nenhum item encontrado no PDF. O marketplace selecionado foi '{marketplace}', verifique o arquivo.")

    # ── FIFO: enforce max 3 active batches ───────────────────────────────────
    active_batches = (
        db.query(Batch)
        .filter(Batch.status == "active")
        .order_by(Batch.full_date.asc(), Batch.seq.asc())
        .all()
    )

    if len(active_batches) >= MAX_ACTIVE_BATCHES:
        oldest = active_batches[0]

        if force_archive_batch_id and force_archive_batch_id == oldest.id:
            # User confirmed → archive and proceed
            _archive_batch(oldest, db)
        else:
            # Check pending items in oldest batch
            pending_count = (
                db.query(PickingItem)
                .join(Session, Session.id == PickingItem.session_id)
                .filter(
                    Session.batch_id == oldest.id,
                    PickingItem.status.in_(["pending", "in_progress"])
                )
                .count()
            )
            if pending_count > 0:
                return {
                    "status": "needs_confirmation",
                    "msg": f"O lote mais antigo '{oldest.name}' ainda tem {pending_count} item(ns) pendente(s). Deseja arquivá-lo?",
                    "oldest_batch_id": oldest.id,
                    "oldest_batch_name": oldest.name,
                    "pending_count": pending_count,
                }
            else:
                _archive_batch(oldest, db)

    # ── Create new Batch ─────────────────────────────────────────────────────
    existing_same_date = (
        db.query(Batch)
        .filter(Batch.full_date == batch_date, Batch.status == "active")
        .count()
    )
    seq = existing_same_date + 1
    date_str = batch_date.strftime("%d/%m/%Y")
    batch_name = date_str if seq == 1 else f"{date_str} · nº{seq}"
    new_batch = Batch(
        full_date=batch_date,
        seq=seq,
        name=batch_name,
        marketplace=marketplace,
        status="active",
        created_at=datetime.utcnow(),
    )
    db.add(new_batch)
    db.flush()

    # ── Build session code prefix ─────────────────────────────────────────────
    mp_prefix = "SH" if marketplace == "shopee" else "ML"
    prefix = f"{mp_prefix}-{_date_to_prefix(batch_date)}"
    if seq > 1:
        prefix = f"{prefix}-{chr(64 + seq)}"  # -B, -C, ...

    # ── Split PDF into picking lists ─────────────────────────────────────────
    batches_split = split_into_batches(items_data, max_units=1000)

    added_barcodes: set[tuple[str, str]] = set(
        (r[0], r[1]) for r in db.query(Barcode.barcode, Barcode.sku).all()
    )

    def add_barcode_safe(barcode: str, sku: str, is_primary: bool):
        if barcode and (barcode, sku) not in added_barcodes:
            db.add(Barcode(barcode=barcode, sku=sku, is_primary=is_primary))
            added_barcodes.add((barcode, sku))

    sku_labels: dict[str, list] = {}
    for lbl in labels_data:
        sku_labels.setdefault(lbl["sku"], []).append(lbl)

    created_sessions = []
    total_in_batch = len(batches_split)

    for idx, batch_items in enumerate(batches_split, start=1):
        code = f"{prefix}-L{idx:02d}" if total_in_batch > 1 else prefix
        sess = Session(session_code=code, operator_id=None, status="open", batch_id=new_batch.id, marketplace=marketplace)
        db.add(sess)
        db.flush()

        for item in batch_items:
            sku_norm = (item["sku"] or "").strip().upper()
            pi = PickingItem(
                session_id=sess.id,
                sku=sku_norm,
                ml_code=item.get("ml_code"),
                description=item.get("description", ""),
                qty_required=item["qty_required"],
            )
            db.add(pi)
            add_barcode_safe(sku_norm, sku_norm, True)
            ean = item.get("ean")
            if ean:
                add_barcode_safe(ean, sku_norm, False)

            for lbl in sku_labels.get(item["sku"], []):
                db.add(Label(
                    session_id=sess.id,
                    sku=(lbl["sku"] or "").strip().upper(),
                    label_index=lbl["label_index"],
                    zpl_content=lbl["zpl_content"],
                ))

        created_sessions.append({"session_id": sess.id, "session_code": code, "items": len(batch_items)})

    for entry in get_ml_barcodes(txt_content):
        add_barcode_safe(entry["ml_code"], entry["sku"], False)

    db.commit()
    return {
        "status": "ok",
        "batch_id": new_batch.id,
        "batch_name": batch_name,
        "lists_created": len(created_sessions),
        "total_items": len(items_data),
        "sessions": created_sessions,
    }


# ── Manual extra session ──────────────────────────────────────────────────────

class ManualItemBody(BaseModel):
    sku: str
    qty_required: int
    description: str | None = None
    ml_code: str | None = None  # opcional — relevante quando mesmo SKU tem múltiplos anúncios


class ManualSessionBody(BaseModel):
    batch_id: int
    items: list[ManualItemBody]


@router.post("/manual", status_code=201)
def create_manual_session(body: ManualSessionBody, db: DBSession = Depends(get_db)):
    """Cria uma lista EXTRA dentro de um lote existente, com itens digitados manualmente."""
    if not body.items:
        raise HTTPException(400, "Lista deve ter pelo menos um item")

    batch = db.query(Batch).filter(Batch.id == body.batch_id).first()
    if not batch:
        raise HTTPException(404, "Lote não encontrado")

    skus_norm = [i.sku.strip().upper() for i in body.items]
    if any(not s for s in skus_norm):
        raise HTTPException(400, "SKU inválido")
    if len(skus_norm) != len(set(skus_norm)):
        raise HTTPException(400, "SKU duplicado na mesma lista")
    for it in body.items:
        if it.qty_required is None or it.qty_required <= 0:
            raise HTTPException(400, f"Quantidade inválida para SKU {it.sku}")

    known_skus = {
        (b.sku or "").upper()
        for b in db.query(Barcode).filter(func.upper(Barcode.sku).in_(skus_norm)).all()
    }
    missing = [s for s in skus_norm if s not in known_skus]
    if missing:
        raise HTTPException(400, f"SKU(s) não cadastrado(s) na Base: {', '.join(missing)}")

    mp_prefix = "SH" if batch.marketplace == "shopee" else "ML"
    prefix = f"{mp_prefix}-{_date_to_prefix(batch.full_date)}"
    pattern = f"{prefix}-EXTRA-%"
    existing = (
        db.query(Session.session_code)
        .filter(Session.batch_id == batch.id, Session.session_code.like(pattern))
        .all()
    )
    max_seq = 0
    for (code,) in existing:
        try:
            seq = int(code.rsplit("-EXTRA-", 1)[1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    next_seq = max_seq + 1
    session_code = f"{prefix}-EXTRA-{next_seq:02d}"

    sess = Session(
        session_code=session_code,
        operator_id=None,
        status="open",
        batch_id=batch.id,
        marketplace=batch.marketplace,
    )
    db.add(sess)
    db.flush()

    descriptions = {
        (b.sku or "").upper(): b.description
        for b in db.query(Barcode).filter(
            func.upper(Barcode.sku).in_(skus_norm), Barcode.description.isnot(None)
        ).all()
    }

    for it in body.items:
        sku = it.sku.strip().upper()
        ml_code_norm = (it.ml_code or "").strip().upper() or None
        pi = PickingItem(
            session_id=sess.id,
            sku=sku,
            ml_code=ml_code_norm,
            description=descriptions.get(sku) or it.description or "",
            qty_required=it.qty_required,
        )
        db.add(pi)

    db.commit()
    return {
        "session_id": sess.id,
        "session_code": session_code,
        "items_count": len(body.items),
    }


# ── Claim ─────────────────────────────────────────────────────────────────────

class ClaimBody(BaseModel):
    operator_id: int


@router.post("/{session_id}/claim")
def claim_session(session_id: int, body: ClaimBody, db: DBSession = Depends(get_db)):
    sess = _session_or_404(db, session_id)
    # Já reservada pelo mesmo operador — idempotente, só navega
    if sess.operator_id == body.operator_id:
        return {"session_id": sess.id, "session_code": sess.session_code, "status": sess.status}
    if sess.status != "open" or sess.operator_id is not None:
        raise HTTPException(409, "Lista já está em uso por outro operador")
    sess.operator_id = body.operator_id
    # Não muda status aqui — in_progress só ocorre no primeiro scan
    db.commit()
    return {"session_id": sess.id, "session_code": sess.session_code, "status": sess.status}


# ── List & Get ────────────────────────────────────────────────────────────────

@router.get("/")
def list_sessions(
    marketplace: str | None = Query(None, description="Filtra por marketplace (ex: 'ml', 'shopee')"),
    db: DBSession = Depends(get_db),
):
    # LIMIT removido — o filtro de marketplace no DB evita carregar sessões de outros marketplaces.
    # Bug histórico: LIMIT 100 escondia sessões antigas do painel quando o total cruzava 100.
    q = db.query(Session)
    if marketplace:
        q = q.filter(Session.marketplace == marketplace)
    sessions = q.order_by(Session.id.desc()).all()
    operators = {o.id: o.name for o in db.query(Operator).all()}
    result = []
    for s in sessions:
        total = sum(i.qty_required for i in s.items)
        picked = sum(i.qty_picked for i in s.items)
        unique_sku_count = len({i.sku for i in s.items})
        result.append({
            "id": s.id,
            "session_code": s.session_code,
            "operator_id": s.operator_id,
            "operator_name": operators.get(s.operator_id) if s.operator_id else None,
            "status": s.status,
            "marketplace": s.marketplace, # INJETADO
            "created_at": s.created_at.isoformat(),
            "items_total": total,
            "items_picked": picked,
            "unique_sku_count": unique_sku_count,
        })
    return result


@router.get("/find-by-barcode")
def find_by_barcode(
    barcode: str = Query(...),
    operator_id: int = Query(...),
    db: DBSession = Depends(get_db),
):
    """
    Locate a picking item by barcode across all active sessions.
    Returns the best match (highest qty_required) with an action hint.

    Actions:
      open             — item is pending/in_progress, session available to this operator
      already_done     — item is complete/partial/out_of_stock
      in_progress_other — session is claimed by a different operator
      not_found        — barcode not in the Barcode table
      not_in_sessions  — SKU exists but not in any active session
    """
    # 1. Try exact barcode match — pega TODOS os SKUs vinculados (multi-SKU possível)
    bc_rows = db.query(Barcode).filter(Barcode.barcode == barcode).all()
    skus = list({(r.sku or "").upper() for r in bc_rows})

    # 2. If no barcode match, try SKU or Description (partial match)
    if not skus:
        like_query = f"%{barcode}%"
        # Search for candidates in PickingItem directly
        # Include ALL sessions (even completed) so EXT lists and finished items show up
        from sqlalchemy import case
        barcode_upper = barcode.upper()
        candidates_query = (
            db.query(PickingItem, Session, Operator.name.label("operator_name"))
            .join(Session, Session.id == PickingItem.session_id)
            .outerjoin(Operator, Operator.id == Session.operator_id)
            .filter(
                (func.upper(PickingItem.sku) == barcode_upper) |
                (PickingItem.sku.ilike(like_query)) |
                (PickingItem.description.ilike(like_query))
            )
            .order_by(
                # Prioritize non-completed sessions first
                case((Session.status != "completed", 0), else_=1).asc(),
                case((func.upper(PickingItem.sku) == barcode_upper, 1), else_=0).desc(),  # Exact SKU first
                PickingItem.qty_required.desc()                         # Then by volume
            )
        )

        matches = candidates_query.all()

        if not matches:
             return {"action": "not_found", "barcode": barcode}

        # Deduplicate por (sku, ml_code, session_id) — mantém itens distintos
        # mesmo quando têm o mesmo SKU em sessões/ml_codes diferentes.
        seen_keys = set()
        unique_matches = []
        for m in matches:
            sku_key = (m[0].sku or "").upper()
            ml_key = (m[0].ml_code or "").upper()
            sess_key = m[1].id
            key = (sku_key, ml_key, sess_key)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_matches.append(m)
        matches = unique_matches

        # If the top match is NOT an exact SKU, and there are multiple candidates, return list
        top_item, _, _ = matches[0]
        if (top_item.sku or "").upper() != barcode_upper and len(matches) > 1:
            return {
                "action": "multiple_matches",
                "barcode": barcode,
                "candidates": [
                    {
                        "item_id": m[0].id,
                        "sku": m[0].sku,
                        "ml_code": m[0].ml_code,
                        "description": m[0].description,
                        "session_id": m[1].id,
                        "session_code": m[1].session_code,
                        "operator_name": m[2] or "Disponível",
                        "marketplace": m[1].marketplace,
                        "qty_picked": m[0].qty_picked,
                        "qty_required": m[0].qty_required,
                        "status": m[0].status
                    } for m in matches
                ]
            }

        # Otherwise, take the first one
        skus = [(top_item.sku or "").upper()]

    # 3. Busca itens com QUALQUER um dos SKUs vinculados, em sessões abertas
    rows = (
        db.query(PickingItem, Session, Operator)
        .join(Session, Session.id == PickingItem.session_id)
        .outerjoin(Operator, Operator.id == Session.operator_id)
        .filter(
            func.upper(PickingItem.sku).in_(skus),
            Session.status != "completed",
        )
        .order_by(PickingItem.qty_required.desc())
        .all()
    )

    distinct_skus_in_rows = {(r[0].sku or "").upper() for r in rows}

    # Mostra escolha quando há múltiplos itens em listas abertas — pode ser
    # SKUs diferentes vinculados ao mesmo EAN, OU mesmo SKU em sessões/ml_codes
    # diferentes (ex: PDF ML com mesmo SKU em anúncios distintos).
    if len(rows) > 1:
        return {
            "action": "multiple_matches",
            "barcode": barcode,
            "candidates": [
                {
                    "item_id": r[0].id,
                    "sku": r[0].sku,
                    "ml_code": r[0].ml_code,
                    "description": r[0].description,
                    "session_id": r[1].id,
                    "session_code": r[1].session_code,
                    "operator_name": r[2].name if r[2] else "Disponível",
                    "marketplace": r[1].marketplace,
                    "qty_picked": r[0].qty_picked,
                    "qty_required": r[0].qty_required,
                    "status": r[0].status,
                } for r in rows
            ]
        }

    # Apenas 1 SKU encontrado (ou nenhum) — fluxo single
    sku = next(iter(distinct_skus_in_rows), skus[0])

    if not rows:
        # Verificar se algum dos SKUs vinculados foi concluído em sessão finalizada
        done_rows = (
            db.query(PickingItem, Session, Operator)
            .join(Session, Session.id == PickingItem.session_id)
            .outerjoin(Operator, Operator.id == Session.operator_id)
            .filter(
                func.upper(PickingItem.sku).in_(skus),
                Session.status == "completed",
                PickingItem.status.in_(["complete", "partial", "out_of_stock"]),
            )
            .order_by(Session.id.desc())
            .first()
        )
        if done_rows:
            done_item, done_session, done_operator = done_rows
            return {
                "action": "already_done",
                "sku": sku,
                "barcode": barcode,
                "best_match": {
                    "session_id": done_session.id,
                    "session_code": done_session.session_code,
                    "item_status": done_item.status,
                    "qty_required": done_item.qty_required,
                    "qty_picked": done_item.qty_picked,
                    "description": done_item.description,
                    "operator_id": done_operator.id if done_operator else None,
                    "operator_name": done_operator.name if done_operator else None,
                    "marketplace": done_session.marketplace, # INJETADO
                },
            }
        return {"action": "not_in_sessions", "sku": sku, "barcode": barcode}

    item, session, operator = rows[0]

    match = {
        "session_id": session.id,
        "session_code": session.session_code,
        "item_status": item.status,
        "qty_required": item.qty_required,
        "qty_picked": item.qty_picked,
        "description": item.description,
        "operator_id": operator.id if operator else None,
        "operator_name": operator.name if operator else None,
        "marketplace": session.marketplace, # INJETADO
        "item_id": item.id
    }

    # 3. Determine action
    terminal = {"complete", "partial", "out_of_stock"}
    if item.status in terminal:
        action = "already_done"
    elif session.operator_id and session.operator_id != operator_id:
        if item.qty_picked == 0:
            action = "transfer_available"
        else:
            action = "in_progress_other"
    else:
        action = "open"

    return {
        "action": action, 
        "sku": item.sku, 
        "barcode": barcode, 
        "best_match": match,
        "item_id": item.id if action == "transfer_available" else item.id,
        "owner_name": operator.name if (operator and action == "transfer_available") else None
    }


@router.get("/shortage-report")
def shortage_report(db: DBSession = Depends(get_db)):
    """
    Retorna todos os SKUs com falta (shortage_qty > 0) de todas as sessões,
    agrupados por (SKU, Lista) para mostrar qual lista originou a falta.
    """
    raw_rows = (
        db.query(
            PickingItem.sku,
            PickingItem.description,
            PickingItem.shortage_qty,
            PickingItem.notes,
            Session.session_code,
            Session.marketplace,
        )
        .join(Session, Session.id == PickingItem.session_id)
        .filter(PickingItem.shortage_qty > 0)
        .order_by(Session.session_code, PickingItem.sku)
        .all()
    )

    # Agrega por (SKU, Lista) — mesmo SKU em listas diferentes aparece separado
    aggregated = {}
    for r in raw_rows:
        key = (r.sku, r.session_code, r.marketplace)
        if key not in aggregated:
            aggregated[key] = {
                "sku": r.sku,
                "description": r.description,
                "session_code": r.session_code,
                "marketplace": r.marketplace,
                "shortage_qty": 0,
                "all_notes": set()
            }
        aggregated[key]["shortage_qty"] += r.shortage_qty
        if r.notes:
            for part in r.notes.split(","):
                p = part.strip()
                if p:
                    aggregated[key]["all_notes"].add(p)

    return [
        {
            "sku": v["sku"],
            "description": v["description"],
            "session_code": v["session_code"],
            "marketplace": v["marketplace"],
            "shortage_qty": v["shortage_qty"],
            "notes": ", ".join(sorted(list(v["all_notes"]))) if v["all_notes"] else None
        }
        for v in aggregated.values()
    ]


@router.get("/all-pending")
def get_all_pending(db: DBSession = Depends(get_db)):
    """
    Returns all items with 'pending' status from all active (non-completed) sessions.
    Ordered by remaining quantity desc.
    Used for the cross-session pending items list.
    """
    rows = (
        db.query(PickingItem, Session, Operator.name.label("operator_name"))
        .join(Session, Session.id == PickingItem.session_id)
        .outerjoin(Operator, Operator.id == Session.operator_id)
        .filter(Session.status != "completed")
        .filter(PickingItem.status == "pending")
        .order_by((PickingItem.qty_required - PickingItem.qty_picked).desc())
        .all()
    )
    return [
        {
            "item_id": r[0].id,
            "sku": r[0].sku,
            "description": r[0].description,
            "session_id": r[1].id,
            "session_code": r[1].session_code,
            "operator_name": r[2] or "Disponível",
            "marketplace": r[1].marketplace, # INJETADO
            "qty_picked": r[0].qty_picked,
            "qty_required": r[0].qty_required,
            "status": r[0].status,
        } for r in rows
    ]


@router.get("/{session_id}")
def get_session(session_id: int, db: DBSession = Depends(get_db)):
    s = _session_or_404(db, session_id)
    progress = svc.session_progress(db, session_id)
    current = svc.get_current_item(db, session_id)
    return {
        "id": s.id,
        "session_code": s.session_code,
        "operator_id": s.operator_id,
        "status": s.status,
        "marketplace": s.marketplace, # INJETADO AQUI
        "progress": progress,
        "current_item": svc._item_dict(current) if current else None,
    }


@router.get("/{session_id}/items")
def list_items(session_id: int, db: DBSession = Depends(get_db)):
    _session_or_404(db, session_id)
    items = db.query(PickingItem).filter(PickingItem.session_id == session_id).all()
    return [svc._item_dict(i) for i in items]


# ── Scan & Actions ────────────────────────────────────────────────────────────

class ScanBody(BaseModel):
    barcode: str
    operator_id: int
    focus_sku: str | None = None


@router.post("/{session_id}/scan")
def scan(session_id: int, body: ScanBody, db: DBSession = Depends(get_db)):
    _session_or_404(db, session_id)
    result = svc.process_scan(db, session_id, body.barcode, body.operator_id, body.focus_sku)
    result["progress"] = svc.session_progress(db, session_id)
    return result


@router.post("/{session_id}/scan-box")
def scan_box(session_id: int, body: ScanBody, db: DBSession = Depends(get_db)):
    """Box mode: one scan marks the full required quantity as picked."""
    _session_or_404(db, session_id)
    result = svc.process_scan_box(db, session_id, body.barcode, body.operator_id, body.focus_sku)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class UndoBody(BaseModel):
    sku: str
    operator_id: int


@router.post("/{session_id}/undo")
def undo(session_id: int, body: UndoBody, db: DBSession = Depends(get_db)):
    result = svc.undo_last_scan(db, session_id, body.sku, body.operator_id)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class ShortageBody(BaseModel):
    sku: str
    qty_found: int
    operator_id: int
    notes: str | None = None


@router.post("/{session_id}/shortage")
def shortage(session_id: int, body: ShortageBody, db: DBSession = Depends(get_db)):
    result = svc.mark_shortage(db, session_id, body.sku, body.qty_found, body.operator_id, body.notes)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class OosBody(BaseModel):
    sku: str
    operator_id: int
    notes: str | None = None


@router.post("/{session_id}/out-of-stock")
def out_of_stock(session_id: int, body: OosBody, db: DBSession = Depends(get_db)):
    result = svc.mark_out_of_stock(db, session_id, body.sku, body.operator_id, body.notes)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class ReopenBody(BaseModel):
    sku: str
    operator_id: int


@router.post("/{session_id}/reopen")
def reopen(session_id: int, body: ReopenBody, db: DBSession = Depends(get_db)):
    result = svc.reopen_item(db, session_id, body.sku, body.operator_id)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class ForceCompleteBody(BaseModel):
    sku: str
    operator_id: int


@router.post("/{session_id}/force-complete")
def force_complete(session_id: int, body: ForceCompleteBody, db: DBSession = Depends(get_db)):
    result = svc.force_complete_item(db, session_id, body.sku, body.operator_id)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class ResetItemBody(BaseModel):
    sku: str
    operator_id: int


@router.post("/{session_id}/reset-item")
def reset_item(session_id: int, body: ResetItemBody, db: DBSession = Depends(get_db)):
    """Reset a single picking item back to qty=0 / pending."""
    _session_or_404(db, session_id)
    result = svc.reset_item(db, session_id, body.sku, body.operator_id)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class ResetAllBody(BaseModel):
    operator_id: int


@router.post("/{session_id}/reset-all-items")
def reset_all_items(session_id: int, body: ResetAllBody, db: DBSession = Depends(get_db)):
    """Reset every item in the session back to qty=0 / pending."""
    _session_or_404(db, session_id)
    result = svc.reset_all_items(db, session_id, body.operator_id)
    result["progress"] = svc.session_progress(db, session_id)
    return result


class AddBarcodeBody(BaseModel):
    barcode: str
    sku: str
    operator_id: int


@router.post("/{session_id}/add-barcode")
def add_barcode(session_id: int, body: AddBarcodeBody, db: DBSession = Depends(get_db)):
    return svc.add_barcode(db, body.barcode, body.sku, body.operator_id)


# ── Reopen session ────────────────────────────────────────────────────────────

@router.post("/{session_id}/reopen-session", status_code=200)
def reopen_session(session_id: int, db: DBSession = Depends(get_db)):
    sess = _session_or_404(db, session_id)
    if sess.status not in ("completed", "in_progress"):
        raise HTTPException(409, "Apenas listas concluídas ou em andamento podem ser reinicializadas")

    # Reseta APENAS itens com problema (out_of_stock / partial). Itens completos preservados.
    problem_items = (
        db.query(PickingItem)
        .filter(PickingItem.session_id == session_id)
        .filter(PickingItem.status.in_(("out_of_stock", "partial")))
        .all()
    )
    reset_skus = []
    for item in problem_items:
        reset_skus.append(item.sku)
        item.qty_picked = 0
        item.shortage_qty = 0
        item.status = "pending"
        item.completed_at = None
        item.labels_printed = False
        item.notes = None

    # Apaga registros de Shortage ligados a esta lista para os SKUs resetados
    if reset_skus:
        db.query(Shortage).filter(
            Shortage.list_id == str(session_id),
            Shortage.sku.in_(reset_skus),
        ).delete(synchronize_session=False)

    sess.status = "open"
    sess.operator_id = None
    sess.completed_at = None
    db.commit()
    logger.info("REOPEN_SESSION session_id=%s items_reset=%d skus=%s",
                session_id, len(problem_items), reset_skus)
    return {
        "session_id": sess.id,
        "status": "open",
        "items_reset": len(problem_items),
        "reset_skus": reset_skus,
    }


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{session_id}", status_code=200)
def delete_session(session_id: int, db: DBSession = Depends(get_db)):
    sess = _session_or_404(db, session_id)
    # Master can delete in_progress
    # Delete children in FK order
    item_ids = [i.id for i in db.query(PickingItem.id).filter(PickingItem.session_id == session_id).all()]
    if item_ids:
        db.query(ScanEvent).filter(ScanEvent.picking_item_id.in_(item_ids)).delete(synchronize_session=False)
    db.query(PrintJob).filter(PrintJob.session_id == session_id).delete(synchronize_session=False)
    db.query(Label).filter(Label.session_id == session_id).delete(synchronize_session=False)
    db.query(PickingItem).filter(PickingItem.session_id == session_id).delete(synchronize_session=False)
    db.delete(sess)
    db.commit()
    return {"status": "ok"}


class TransferBody(BaseModel):
    item_id: int
    operator_id: int

@router.post("/transfer", status_code=201)
def transfer_item_api(body: TransferBody, db: DBSession = Depends(get_db)):
    """
    Endpoint to trigger an item reallocation.
    Used by both scan auto-transfer and Supervisor manual transfer.
    """
    try:
        new_sess = svc.reallocate_item(db, body.item_id, body.operator_id)
        return {
            "status": "ok",
            "new_session_id": new_sess.id,
            "new_session_code": new_sess.session_code
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Erro ao transferir item")
        raise HTTPException(500, "Erro interno ao processar transferência")


class UpdateNotesBody(BaseModel):
    notes: str | None

@router.patch("/items/{item_id}/notes")
def update_item_notes(item_id: int, body: UpdateNotesBody, db: DBSession = Depends(get_db)):
    return svc.update_item_notes(db, item_id, body.notes)


class UpdateSkuNotesBody(BaseModel):
    notes: str | None

@router.patch("/shortage-report/{sku}/notes")
def update_sku_notes_api(sku: str, body: UpdateSkuNotesBody, db: DBSession = Depends(get_db)):
    return svc.update_sku_notes(db, sku, body.notes)


def _session_or_404(db: DBSession, session_id: int) -> Session:
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(404, "Sessão não encontrada")
    return s

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from database import SessionLocal
from models import OrderOperational, SyncRun, TinyOrderItem, TinyOrderSync
from mas_core.agent_protocol import ALLOWED_SALES_STATUS
from services.tiny_service import TinyService

log = logging.getLogger(__name__)

OLIST_OPERATIONAL_BUCKET = {"faturado", "pronto para envio", "enviado", "entregue"}
SYNC_LOCK = asyncio.Lock()
SCHEDULER_TASK: asyncio.Task | None = None
SCHEDULER_STOP = False


def _utcnow() -> datetime:
    return datetime.utcnow()


def _parse_br_date(raw_value: Any) -> Optional[str]:
    value = str(raw_value or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _extract_channel(payload: Dict[str, Any]) -> Optional[str]:
    ecommerce = payload.get("ecommerce")
    if isinstance(ecommerce, dict):
        return ecommerce.get("nomeEcommerce")
    if ecommerce:
        return str(ecommerce)
    return None


def _normalize_status(raw_status: Any) -> str:
    return str(raw_status or "em_aberto").strip().lower()


def _build_status_bucket(status: str) -> str:
    if status in OLIST_OPERATIONAL_BUCKET:
        return "olist_operacional"
    if status in {"cancelado", "cancelada", "cancelado parcialmente", "cancelado_parcialmente"}:
        return "cancelado"
    if status in {"dados incompletos", "em aberto", "em_aberto"}:
        return "pendencia"
    return "outros"


def _calculate_total_value(payload: Dict[str, Any]) -> float:
    total = _safe_float(payload.get("total_pedido"))
    if total > 0:
        return round(total, 2)

    items = payload.get("itens", [])
    running_total = 0.0
    for item_obj in items:
        item_data = item_obj.get("item", {})
        running_total += _safe_float(item_data.get("quantidade")) * _safe_float(item_data.get("valor_unitario"))
    return round(running_total, 2)


def _upsert_raw_order(db, payload: Dict[str, Any], synced_at: datetime) -> str:
    order_id = str(payload.get("id") or "").strip()
    if not order_id:
        raise ValueError("pedido sem id")

    ecommerce_name = _extract_channel(payload)
    marcadores = payload.get("marcadores", [])

    existing = db.query(TinyOrderSync).filter(TinyOrderSync.id == order_id).first()
    action = "updated" if existing else "inserted"
    if not existing:
        existing = TinyOrderSync(id=order_id)
        db.add(existing)

    existing.numero = payload.get("numero")
    existing.ecommerce = ecommerce_name
    existing.marcadores_json = json.dumps(marcadores, ensure_ascii=False)
    existing.raw_data = json.dumps(payload, ensure_ascii=False)
    existing.last_synced_at = synced_at

    db.query(TinyOrderItem).filter(TinyOrderItem.tiny_order_id == order_id).delete()
    for item_obj in payload.get("itens", []):
        item_data = item_obj.get("item", {})
        db.add(
            TinyOrderItem(
                tiny_order_id=order_id,
                id_produto=item_data.get("id_produto"),
                codigo=item_data.get("codigo"),
                descricao=item_data.get("descricao"),
                quantidade=_safe_float(item_data.get("quantidade")),
                valor_unitario=_safe_float(item_data.get("valor_unitario")),
            )
        )
    return action


def _upsert_operational_order(db, payload: Dict[str, Any], synced_at: datetime) -> None:
    order_id = str(payload.get("id") or "").strip()
    status = _normalize_status(payload.get("situacao"))
    record = db.query(OrderOperational).filter(OrderOperational.order_id == order_id).first()
    if not record:
        record = OrderOperational(order_id=order_id)
        db.add(record)

    record.numero = payload.get("numero")
    record.channel = _extract_channel(payload)
    record.order_date = _parse_br_date(payload.get("data_pedido"))
    record.invoice_date = _parse_br_date(payload.get("data_faturamento"))
    record.shipping_date = _parse_br_date(payload.get("data_envio"))
    record.delivery_date = _parse_br_date(payload.get("data_entrega"))
    record.current_status = status
    record.status_bucket = _build_status_bucket(status)
    record.is_operational_sale = status in ALLOWED_SALES_STATUS
    record.total_value = _calculate_total_value(payload)
    record.item_count = len(payload.get("itens", []))
    record.source_name = "tiny_api"
    record.last_source_update_at = synced_at
    record.last_synced_at = synced_at


def _create_sync_run(db, sync_type: str, window_start: str, window_end: str, notes: Optional[str] = None) -> SyncRun:
    run = SyncRun(
        sync_type=sync_type,
        status="running",
        window_start=window_start,
        window_end=window_end,
        notes=notes,
        updated_at=_utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def recover_stale_runs() -> int:
    db = SessionLocal()
    try:
        stale_runs = db.query(SyncRun).filter(SyncRun.status == "running").all()
        for run in stale_runs:
            run.status = "aborted"
            run.finished_at = _utcnow()
            run.notes = ((run.notes or "") + " | encerrado no startup por recuperação de estado").strip(" |")
        db.commit()
        return len(stale_runs)
    finally:
        db.close()


def _finish_sync_run(db, run_id: int, *, status: str, orders_seen: int, orders_inserted: int, orders_updated: int, orders_failed: int, notes: str) -> None:
    run = db.query(SyncRun).filter(SyncRun.id == run_id).first()
    if not run:
        return
    run.status = status
    run.orders_seen = orders_seen
    run.orders_inserted = orders_inserted
    run.orders_updated = orders_updated
    run.orders_failed = orders_failed
    run.notes = notes
    run.updated_at = _utcnow()
    run.finished_at = _utcnow()
    db.commit()


def _update_sync_run_progress(
    db,
    run_id: int,
    *,
    orders_seen: int,
    orders_inserted: int,
    orders_updated: int,
    orders_failed: int,
    notes: str,
) -> None:
    run = db.query(SyncRun).filter(SyncRun.id == run_id).first()
    if not run:
        return
    run.orders_seen = orders_seen
    run.orders_inserted = orders_inserted
    run.orders_updated = orders_updated
    run.orders_failed = orders_failed
    run.notes = notes
    run.updated_at = _utcnow()
    db.commit()


async def sync_order_ids(token: str, order_ids: Iterable[str], sync_type: str = "manual") -> Dict[str, Any]:
    order_ids = [str(order_id) for order_id in order_ids if order_id]
    if not order_ids:
        return {"status": "noop", "sync_type": sync_type, "orders_seen": 0}

    async with SYNC_LOCK:
        svc = TinyService(token)
        db = SessionLocal()
        now = _utcnow()
        run = _create_sync_run(
            db,
            sync_type=sync_type,
            window_start=now.strftime("%Y-%m-%d"),
            window_end=now.strftime("%Y-%m-%d"),
            notes=f"sync por ids ({len(order_ids)} pedidos)",
        )
        inserted = 0
        updated = 0
        failed = 0

        try:
            for order_id in order_ids:
                try:
                    await asyncio.sleep(0.35)
                    details_resp = await svc.get_order_details(order_id)
                    payload = details_resp.get("pedido", {})
                    if not payload:
                        failed += 1
                        continue
                    synced_at = _utcnow()
                    action = _upsert_raw_order(db, payload, synced_at)
                    _upsert_operational_order(db, payload, synced_at)
                    db.commit()
                    if action == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                except Exception as exc:
                    failed += 1
                    db.rollback()
                    log.exception("Falha ao sincronizar pedido %s: %s", order_id, exc)

            _finish_sync_run(
                db,
                run.id,
                status="success" if failed == 0 else "partial",
                orders_seen=len(order_ids),
                orders_inserted=inserted,
                orders_updated=updated,
                orders_failed=failed,
                notes=f"sync por ids concluído ({sync_type})",
            )
            return {
                "status": "success" if failed == 0 else "partial",
                "sync_type": sync_type,
                "orders_seen": len(order_ids),
                "orders_inserted": inserted,
                "orders_updated": updated,
                "orders_failed": failed,
                "run_id": run.id,
            }
        except Exception as exc:
            db.rollback()
            _finish_sync_run(
                db,
                run.id,
                status="error",
                orders_seen=len(order_ids),
                orders_inserted=inserted,
                orders_updated=updated,
                orders_failed=failed + 1,
                notes=f"erro fatal: {exc}",
            )
            raise
        finally:
            db.close()


async def _run_date_range_sync(
    token: str,
    *,
    start_dt: datetime,
    end_dt: datetime,
    sync_type: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    async with SYNC_LOCK:
        svc = TinyService(token)
        db = SessionLocal()
        window_start = start_dt.strftime("%Y-%m-%d")
        window_end = end_dt.strftime("%Y-%m-%d")
        run = _create_sync_run(db, sync_type=sync_type, window_start=window_start, window_end=window_end, notes=note)
        inserted = 0
        updated = 0
        failed = 0

        try:
            response = await svc.search_orders(
                data_inicial=start_dt.strftime("%d/%m/%Y"),
                data_final=end_dt.strftime("%d/%m/%Y"),
            )
            orders = response.get("pedidos", []) if isinstance(response, dict) else []
            order_ids: list[str] = []
            for item in orders:
                pedido = item.get("pedido", {}) if isinstance(item, dict) else {}
                order_id = pedido.get("id")
                if order_id:
                    order_ids.append(str(order_id))

            deduped_ids = list(dict.fromkeys(order_ids))
            for order_id in deduped_ids:
                try:
                    await asyncio.sleep(0.35)
                    details_resp = await svc.get_order_details(order_id)
                    payload = details_resp.get("pedido", {})
                    if not payload:
                        failed += 1
                        continue
                    synced_at = _utcnow()
                    action = _upsert_raw_order(db, payload, synced_at)
                    _upsert_operational_order(db, payload, synced_at)
                    db.commit()
                    if action == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                except Exception as exc:
                    failed += 1
                    db.rollback()
                    log.exception("Falha em %s (%s): %s", sync_type, order_id, exc)

            canonical_count = (
                db.query(OrderOperational)
                .filter(OrderOperational.order_date >= window_start, OrderOperational.order_date <= window_end)
                .count()
            )
            _finish_sync_run(
                db,
                run.id,
                status="success" if failed == 0 else "partial",
                orders_seen=len(deduped_ids),
                orders_inserted=inserted,
                orders_updated=updated,
                orders_failed=failed,
                notes=f"{sync_type} concluído. canônico na janela: {canonical_count}",
            )
            return {
                "status": "success" if failed == 0 else "partial",
                "sync_type": sync_type,
                "orders_seen": len(deduped_ids),
                "orders_inserted": inserted,
                "orders_updated": updated,
                "orders_failed": failed,
                "canonical_window_count": canonical_count,
                "run_id": run.id,
            }
        except Exception as exc:
            db.rollback()
            _finish_sync_run(
                db,
                run.id,
                status="error",
                orders_seen=0,
                orders_inserted=inserted,
                orders_updated=updated,
                orders_failed=failed + 1,
                notes=f"erro fatal: {exc}",
            )
            raise
        finally:
            db.close()


async def run_window_sync(token: str, *, lookback_days: int, sync_type: str, note: Optional[str] = None) -> Dict[str, Any]:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)
    return await _run_date_range_sync(
        token,
        start_dt=start_dt,
        end_dt=end_dt,
        sync_type=sync_type,
        note=note,
    )


async def run_batched_full_sync(
    token: str,
    *,
    lookback_days: int,
    chunk_days: int = 7,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    started_at = _utcnow()
    parent_run = _create_sync_run(
        db,
        sync_type="full_load",
        window_start=(datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d"),
        window_end=datetime.now().strftime("%Y-%m-%d"),
        notes=note or f"carga inicial em blocos de {chunk_days} dias",
    )
    db.close()

    total_seen = 0
    total_inserted = 0
    total_updated = 0
    total_failed = 0
    chunk_results: list[str] = []

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=lookback_days)
    chunk_start = start_dt
    total_chunks = max(1, ((lookback_days - 1) // chunk_days) + 1)
    completed_chunks = 0

    try:
        while chunk_start <= end_dt:
            chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_dt)
            chunk_note = f"bloco {chunk_start.strftime('%d/%m')} a {chunk_end.strftime('%d/%m')}"
            db = SessionLocal()
            _update_sync_run_progress(
                db,
                parent_run.id,
                orders_seen=total_seen,
                orders_inserted=total_inserted,
                orders_updated=total_updated,
                orders_failed=total_failed,
                notes=(
                    (note or "carga inicial em blocos")
                    + f" | progresso {completed_chunks}/{total_chunks}"
                    + f" | processando bloco {completed_chunks + 1}/{total_chunks}: {chunk_start.strftime('%d/%m')}..{chunk_end.strftime('%d/%m')}"
                ),
            )
            db.close()
            result = await _run_date_range_sync(
                token,
                start_dt=chunk_start,
                end_dt=chunk_end,
                sync_type="full_load_chunk",
                note=chunk_note,
            )
            total_seen += int(result.get("orders_seen") or 0)
            total_inserted += int(result.get("orders_inserted") or 0)
            total_updated += int(result.get("orders_updated") or 0)
            total_failed += int(result.get("orders_failed") or 0)
            completed_chunks += 1
            chunk_results.append(
                f"{chunk_start.strftime('%Y-%m-%d')}..{chunk_end.strftime('%Y-%m-%d')}={result.get('status')}"
            )
            db = SessionLocal()
            _update_sync_run_progress(
                db,
                parent_run.id,
                orders_seen=total_seen,
                orders_inserted=total_inserted,
                orders_updated=total_updated,
                orders_failed=total_failed,
                notes=(
                    (note or "carga inicial em blocos")
                    + f" | progresso {completed_chunks}/{total_chunks}"
                    + f" | ultimo bloco {chunk_start.strftime('%d/%m')}..{chunk_end.strftime('%d/%m')}={result.get('status')}"
                ),
            )
            db.close()
            chunk_start = chunk_end + timedelta(days=1)

        db = SessionLocal()
        _finish_sync_run(
            db,
            parent_run.id,
            status="success" if total_failed == 0 else "partial",
            orders_seen=total_seen,
            orders_inserted=total_inserted,
            orders_updated=total_updated,
            orders_failed=total_failed,
            notes=(note or "carga inicial em blocos") + " | " + "; ".join(chunk_results),
        )
        db.close()
        return {
            "status": "success" if total_failed == 0 else "partial",
            "sync_type": "full_load",
            "orders_seen": total_seen,
            "orders_inserted": total_inserted,
            "orders_updated": total_updated,
            "orders_failed": total_failed,
            "run_id": parent_run.id,
        }
    except Exception as exc:
        db = SessionLocal()
        _finish_sync_run(
            db,
            parent_run.id,
            status="error",
            orders_seen=total_seen,
            orders_inserted=total_inserted,
            orders_updated=total_updated,
            orders_failed=total_failed + 1,
            notes=f"erro fatal no full load em blocos: {exc}",
        )
        db.close()
        raise


def get_sync_snapshot(limit: int = 10) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        runs = db.query(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit).all()
        payload = [
            {
                "id": run.id,
                "sync_type": run.sync_type,
                "status": run.status,
                "window_start": run.window_start,
                "window_end": run.window_end,
                "orders_seen": run.orders_seen,
                "orders_inserted": run.orders_inserted,
                "orders_updated": run.orders_updated,
                "orders_failed": run.orders_failed,
                "notes": run.notes,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "updated_at": run.updated_at.isoformat() if getattr(run, "updated_at", None) else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
            for run in runs
        ]
        canonical_total = db.query(OrderOperational).count()
        raw_total = db.query(TinyOrderSync).count()
        return {
            "runs": payload,
            "canonical_total": canonical_total,
            "raw_total": raw_total,
            "scheduler_running": bool(SCHEDULER_TASK and not SCHEDULER_TASK.done()),
            "sync_in_progress": SYNC_LOCK.locked(),
        }
    finally:
        db.close()


async def scheduler_loop(token: str) -> None:
    global SCHEDULER_STOP
    interval_minutes = int(os.getenv("SYNC_INCREMENTAL_INTERVAL_MINUTES", "10"))
    incremental_days = int(os.getenv("SYNC_INCREMENTAL_LOOKBACK_DAYS", "3"))
    reconciliation_days = int(os.getenv("SYNC_RECONCILIATION_LOOKBACK_DAYS", "30"))
    reconciliation_every_hours = int(os.getenv("SYNC_RECONCILIATION_EVERY_HOURS", "12"))
    next_reconciliation = _utcnow()

    while not SCHEDULER_STOP:
        try:
            await run_window_sync(
                token,
                lookback_days=incremental_days,
                sync_type="incremental",
                note="scheduler incremental",
            )
            if _utcnow() >= next_reconciliation:
                await run_window_sync(
                    token,
                    lookback_days=reconciliation_days,
                    sync_type="reconciliation",
                    note="scheduler reconciliation",
                )
                next_reconciliation = _utcnow() + timedelta(hours=reconciliation_every_hours)
        except Exception as exc:
            log.exception("Falha no scheduler de sync: %s", exc)
        await asyncio.sleep(max(interval_minutes, 1) * 60)


def start_local_scheduler(token: str) -> asyncio.Task | None:
    global SCHEDULER_TASK, SCHEDULER_STOP
    if not token:
        log.warning("Scheduler local não iniciado: TINY_API_TOKEN ausente")
        return None
    if SCHEDULER_TASK and not SCHEDULER_TASK.done():
        return SCHEDULER_TASK
    SCHEDULER_STOP = False
    SCHEDULER_TASK = asyncio.create_task(scheduler_loop(token))
    log.info("Scheduler local de sync iniciado")
    return SCHEDULER_TASK


async def stop_local_scheduler() -> None:
    global SCHEDULER_TASK, SCHEDULER_STOP
    SCHEDULER_STOP = True
    if SCHEDULER_TASK and not SCHEDULER_TASK.done():
        SCHEDULER_TASK.cancel()
        try:
            await SCHEDULER_TASK
        except asyncio.CancelledError:
            pass
    SCHEDULER_TASK = None

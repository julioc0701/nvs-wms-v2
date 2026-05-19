"""Worker assíncrono pra sincronizar o marcador 'SemEstoque' no Tiny.

Fluxo:
1. Hook em _check_and_advance_doc_statuses detecta transição:
   - X → sem_estoque  → enqueue_add(sep_id)
   - sem_estoque → X  → enqueue_remove(sep_id)
2. Worker single-thread processa fila com sleep entre chamadas (rate limit Tiny).
3. Status persistido em TinySeparationStatus.marker_status (processando/ok/erro).
4. Retry SOMENTE manual (via endpoint POST /retry-marker) — evita marcador duplicado.
5. Ao restart do backend: rows com marker_status='processando' são reenfileiradas.

Idempotência: o marcador no Tiny "soma aos demais" — não duplica se o nome é o mesmo.
Mas erro de conexão durante a chamada pode deixar estado inconsistente, então o retry
é manual e a UI mostra o erro pra Master investigar.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from database import SessionLocal
from models import TinySeparationStatus, TinySeparationHeader
from services.tiny_service import TinyService, MARCADOR_SEM_ESTOQUE

log = logging.getLogger(__name__)

# Operações suportadas
OP_ADD = "add"
OP_REMOVE = "remove"

# Fila singleton (criada lazy no primeiro uso). Tuplas: (op, separation_id)
_QUEUE: Optional[asyncio.Queue] = None
_WORKER_TASK: Optional[asyncio.Task] = None
_STOP = False

# Sleep entre chamadas pra respeitar rate limit do Tiny
SLEEP_BETWEEN_CALLS = float(os.getenv("MARKER_SLEEP_SECONDS", "0.4"))


def _get_queue() -> asyncio.Queue:
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = asyncio.Queue()
    return _QUEUE


def enqueue_add(separation_id: str) -> None:
    """Enfileira ADIÇÃO de marcador. Marca status='processando' no DB.
    Pode ser chamado de contexto sync (não usa await)."""
    _mark_processando(separation_id)
    try:
        _get_queue().put_nowait((OP_ADD, separation_id))
        log.info(f"[MARKER_SYNC] ENQUEUE add sep_id={separation_id}")
    except Exception as exc:
        log.exception(f"[MARKER_SYNC] Falha ao enfileirar add sep_id={separation_id}: {exc}")


def enqueue_remove(separation_id: str) -> None:
    """Enfileira REMOÇÃO de marcador. Marca status='processando' no DB."""
    _mark_processando(separation_id)
    try:
        _get_queue().put_nowait((OP_REMOVE, separation_id))
        log.info(f"[MARKER_SYNC] ENQUEUE remove sep_id={separation_id}")
    except Exception as exc:
        log.exception(f"[MARKER_SYNC] Falha ao enfileirar remove sep_id={separation_id}: {exc}")


def _mark_processando(separation_id: str) -> None:
    """Marca o status local como 'processando' antes de enfileirar.
    Sessão isolada — pode ser chamada de qualquer contexto."""
    db = SessionLocal()
    try:
        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == separation_id
        ).first()
        if record:
            record.marker_status = "processando"
            record.marker_error = None
            db.commit()
    except Exception as exc:
        log.exception(f"[MARKER_SYNC] Falha ao marcar processando sep_id={separation_id}: {exc}")
        db.rollback()
    finally:
        db.close()


def _resolve_id_pedido(separation_id: str, db: DBSession) -> Optional[str]:
    """Resolve idPedido a partir de separation_id via TinySeparationHeader.id_pedido.
    Retorna None se não conseguir resolver (Master vai precisar investigar)."""
    header = db.query(TinySeparationHeader).filter(
        TinySeparationHeader.separation_id == separation_id
    ).first()
    if header and header.id_pedido:
        return str(header.id_pedido)
    return None


async def _process_one(op: str, separation_id: str, token: str) -> None:
    """Processa uma operação. Atualiza TinySeparationStatus.marker_* com o resultado.

    Para OP_REMOVE: tolera ausência de TinySeparationStatus (doc pode ter sido
    revertido pra 'aguardando', deletando o registro). Resolve id_pedido via header
    e chama Tiny mesmo sem record — o ponto é remover o marcador no Tiny."""
    db = SessionLocal()
    try:
        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == separation_id
        ).first()

        if not record and op == OP_ADD:
            log.warning(f"[MARKER_SYNC] ADD sep_id={separation_id} sem TinySeparationStatus — skip")
            return

        id_pedido = _resolve_id_pedido(separation_id, db)
        if not id_pedido:
            msg = "id_pedido não resolvido (header sem idOrigemVinc)"
            log.warning(f"[MARKER_SYNC] {op} sep_id={separation_id}: {msg}")
            if record:
                record.marker_status = "erro"
                record.marker_error = msg
                db.commit()
            return

        service = TinyService(token=token)
        try:
            if op == OP_ADD:
                await service.adicionar_marcador(id_pedido)
            elif op == OP_REMOVE:
                await service.remover_marcador(id_pedido)
            else:
                raise ValueError(f"Operação desconhecida: {op}")

            if record:
                record.marker_status = "ok"
                record.marker_error = None
                record.marker_sent_at = datetime.utcnow()
                db.commit()
            log.info(f"[MARKER_SYNC] OK {op} sep_id={separation_id} id_pedido={id_pedido}")
        except Exception as call_exc:
            err = str(call_exc)[:500]
            if record:
                record.marker_status = "erro"
                record.marker_error = err
                db.commit()
            log.warning(f"[MARKER_SYNC] ERRO {op} sep_id={separation_id} id_pedido={id_pedido}: {err}")

    except Exception as outer:
        log.exception(f"[MARKER_SYNC] Falha inesperada processando sep_id={separation_id}: {outer}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def _recover_in_flight(token: str) -> None:
    """No startup, reenfileira items com marker_status='processando' que ficaram pendurados
    em um restart anterior. Idempotente — apenas força reexecução."""
    db = SessionLocal()
    try:
        stale = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.marker_status == "processando"
        ).all()
        if not stale:
            return
        log.info(f"[MARKER_SYNC] Recovery: {len(stale)} item(s) 'processando' do restart anterior")
        for record in stale:
            # Determina operação esperada pelo status do doc atual
            op = OP_ADD if record.status == "sem_estoque" else OP_REMOVE
            _get_queue().put_nowait((op, record.separation_id))
    except Exception as exc:
        log.exception(f"[MARKER_SYNC] Falha no recovery: {exc}")
    finally:
        db.close()


async def marker_sync_loop(token: str) -> None:
    """Loop principal do worker. Roda enquanto _STOP for False.
    - Pega item da fila (bloqueia até ter).
    - Processa.
    - Aguarda SLEEP_BETWEEN_CALLS pra rate limit.
    """
    global _STOP
    enabled = os.getenv("ENABLE_MARKER_SYNC", "true").lower() == "true"
    if not enabled:
        log.info("[MARKER_SYNC] DESABILITADO via ENABLE_MARKER_SYNC=false")
        return

    log.info(f"[MARKER_SYNC] Worker iniciado — sleep entre chamadas: {SLEEP_BETWEEN_CALLS}s")
    await _recover_in_flight(token)

    queue = _get_queue()
    while not _STOP:
        try:
            op, sep_id = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            continue  # checa _STOP de novo
        except Exception as exc:
            log.exception(f"[MARKER_SYNC] Erro pegando da fila: {exc}")
            await asyncio.sleep(1)
            continue

        try:
            await _process_one(op, sep_id, token)
        finally:
            queue.task_done()
            await asyncio.sleep(SLEEP_BETWEEN_CALLS)


def request_stop() -> None:
    """Sinaliza pro loop parar (no shutdown do scheduler)."""
    global _STOP
    _STOP = True

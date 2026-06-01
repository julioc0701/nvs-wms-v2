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
from models import TinySeparationStatus, TinySeparationHeader, TinyPickingListItem, TinyOrderItem
from services.tiny_service import TinyService, MARCADOR_SEM_ESTOQUE, MARCADOR_AJUSTADO

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


def _get_shortage_skus(separation_id: str, db: DBSession) -> list:
    """SKUs em falta (is_shortage) cujos itens consolidados incluem este separation_id.
    A lista de picking consolida vários docs por SKU, então filtramos pelo doc."""
    items = db.query(TinyPickingListItem).filter(
        TinyPickingListItem.is_shortage == True  # noqa: E712
    ).all()
    skus = []
    for it in items:
        if not it.source_separation_ids or not it.sku:
            continue
        seps = [s.strip() for s in it.source_separation_ids.split(",")]
        if separation_id in seps:
            skus.append(it.sku)
    return list(dict.fromkeys(skus))  # dedupe preservando ordem


async def _resolve_id_produto(id_pedido: str, separation_id: str, sku: str,
                              db: DBSession, service: TinyService) -> Optional[str]:
    """Resolve o id_produto do Tiny a partir do SKU. Primeiro no espelho local
    (tiny_order_items, já populado pelo robô de detalhe do pedido) — zero chamada
    extra. Fallback: separacao.obter.php, que retorna idProduto por item."""
    row = db.query(TinyOrderItem).filter(
        TinyOrderItem.tiny_order_id == str(id_pedido),
        TinyOrderItem.codigo == sku,
    ).first()
    if row and row.id_produto:
        return str(row.id_produto)

    try:
        data = await service.get_separation_details(str(separation_id))
        itens = data.get("separacao", {}).get("itens", []) if isinstance(data, dict) else []
        for it in itens:
            if it.get("codigo") == sku:
                pid = it.get("idProduto") or it.get("id_produto")
                if pid:
                    return str(pid)
    except Exception as exc:
        log.warning(f"[MARKER_SYNC] fallback id_produto falhou sku={sku} sep={separation_id}: {exc}")
    return None


async def _adjust_and_mark(service: TinyService, id_pedido: str, separation_id: str, db: DBSession) -> None:
    """Zera o estoque dos SKUs em falta deste doc e troca o marcador
    'Sem Estoque' por 'Gertrudez ajustou estoque'. Itens com estoque não são tocados."""
    skus = _get_shortage_skus(separation_id, db)
    log.info(f"[MARKER_SYNC] ajuste estoque sep_id={separation_id} pedido={id_pedido} skus_falta={skus}")
    for sku in skus:
        id_produto = await _resolve_id_produto(id_pedido, separation_id, sku, db, service)
        if not id_produto:
            log.warning(f"[MARKER_SYNC] id_produto não resolvido sku={sku} pedido={id_pedido} — pula ajuste")
            continue
        await service.atualizar_estoque(id_produto)
        log.info(f"[MARKER_SYNC] estoque zerado sku={sku} id_produto={id_produto} pedido={id_pedido}")
        await asyncio.sleep(SLEEP_BETWEEN_CALLS)
    # Troca marcador: remove o antigo (idempotente) e adiciona o de ajustado
    await service.remover_marcador(id_pedido, MARCADOR_SEM_ESTOQUE)
    await asyncio.sleep(SLEEP_BETWEEN_CALLS)
    await service.adicionar_marcador(id_pedido, MARCADOR_AJUSTADO)


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
                # Doc entrou em sem_estoque: zera estoque dos itens em falta
                # e troca o marcador 'Sem Estoque' por 'Gertrudez ajustou estoque'.
                await _adjust_and_mark(service, id_pedido, separation_id, db)
            elif op == OP_REMOVE:
                # Doc saiu de sem_estoque (desfazer): limpa ambos marcadores.
                # OBS: NÃO restaura o estoque zerado no Tiny (decisão pendente).
                await service.remover_marcador(id_pedido, MARCADOR_SEM_ESTOQUE)
                await asyncio.sleep(SLEEP_BETWEEN_CALLS)
                await service.remover_marcador(id_pedido, MARCADOR_AJUSTADO)
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

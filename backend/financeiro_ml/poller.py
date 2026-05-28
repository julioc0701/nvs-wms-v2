"""Poller periódico: a cada ~6h enfileira 1 PollTask por seller cobrindo os
últimos 14 dias (janela fresca). Delta é leve; offset dá conta (<1000)."""
import asyncio
import logging
import os
from datetime import date, timedelta

from financeiro_ml.worker import PollTask
from financeiro_ml.freshness import FRESH_WINDOW_DAYS

log = logging.getLogger("financeiro_ml.poller")

POLL_INTERVAL_SEC = int(os.getenv("FINANCEIRO_ML_POLL_INTERVAL_SEC", str(6 * 3600)))


def active_sellers(session_factory) -> list[int]:
    from financeiro_ml.models_v2 import MLTokens
    s = session_factory()
    try:
        return [r.seller_id for r in s.query(MLTokens).all()]
    finally:
        s.close()


def build_poll_tasks(sellers: list[int], *, today: date) -> list[PollTask]:
    start = today - timedelta(days=FRESH_WINDOW_DAYS - 1)
    days = [start + timedelta(days=i) for i in range(FRESH_WINDOW_DAYS)]
    return [PollTask(seller_id=sid, days=days) for sid in sellers]


async def poller_loop(session_factory, queue: asyncio.Queue, *, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            sellers = active_sellers(session_factory)
            for task in build_poll_tasks(sellers, today=date.today()):
                await queue.put(task)
            log.info("poller.enqueued sellers=%s", sellers)
        except Exception:
            log.exception("poller.loop_error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass

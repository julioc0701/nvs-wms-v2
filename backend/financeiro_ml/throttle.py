"""Throttle por seller (substitui o global do client.py como gate primário).
~3 req/s/seller (min_interval ~0.33s). Buckets isolados por seller_id."""
import asyncio


class SellerThrottle:
    def __init__(self, min_interval_sec: float = 0.33):
        self._interval = min_interval_sec
        self._last: dict[int, float] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _now(self) -> float:
        return asyncio.get_event_loop().time()

    def _lock_for(self, seller_id: int) -> asyncio.Lock:
        if seller_id not in self._locks:
            self._locks[seller_id] = asyncio.Lock()
        return self._locks[seller_id]

    async def wait(self, *, seller_id: int) -> None:
        async with self._lock_for(seller_id):
            last = self._last.get(seller_id, 0.0)
            delta = self._now() - last
            if delta < self._interval:
                await asyncio.sleep(self._interval - delta)
            self._last[seller_id] = self._now()


import time


class SellerCircuitBreaker:
    """Por seller: closed → (trip) open por cooldown → half-open (deixa 1 passar)
    → success reseta p/ closed. Reabre sozinho, não fica preso até o próximo ciclo."""
    def __init__(self, *, cooldown_sec: int = 300, clock=None):
        self._cooldown = cooldown_sec
        self._opened_at: dict[int, float] = {}
        self._clock = clock or time.monotonic

    def is_open(self, *, seller_id: int) -> bool:
        opened = self._opened_at.get(seller_id)
        if opened is None:
            return False
        if self._clock() - opened >= self._cooldown:
            return False  # half-open: permite 1 tentativa de teste
        return True

    def trip(self, *, seller_id: int) -> None:
        self._opened_at[seller_id] = self._clock()

    def record_success(self, *, seller_id: int) -> None:
        self._opened_at.pop(seller_id, None)

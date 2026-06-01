"""Política de freshness multi-seller. Decide quais dias re-sincronizar.

Regras (migra a política do v1, + next_retry_at do backoff):
- dia sem status                         → sync
- status != ok/imported_unverified e antes do next_retry_at  → skip (backoff)
- status != ok (failed/rate_limited/partial) e já passou retry → sync
- status == imported_unverified          → sync (precisa confirmar contagem real)
- dia == hoje e ok e cache > 5min        → sync
- dia recente (<=14d) e ok e cache > 24h → sync
- dia antigo e ok                        → skip
"""
import os
from datetime import date, datetime, timedelta

# Janela de dias frescos que o poller varre por ciclo + threshold de "recente".
# 7 por padrão (era 14): metade do volume por ciclo. Tunável por env sem deploy.
FRESH_WINDOW_DAYS = int(os.getenv("FINANCEIRO_ML_FRESH_WINDOW_DAYS", "7"))


def days_needing_sync(days: list[date], statuses: dict) -> list[date]:
    today = date.today()
    threshold_recent = today - timedelta(days=FRESH_WINDOW_DAYS)
    now = datetime.utcnow()
    needed = []
    for d in days:
        st = statuses.get(d)
        if st is None:
            needed.append(d); continue
        if st.status == "imported_unverified":
            needed.append(d); continue
        if st.status != "ok":
            nr = getattr(st, "next_retry_at", None)
            if nr is None or nr <= now:
                needed.append(d)
            continue
        if d == today:
            if now - st.last_synced_at > timedelta(minutes=5):
                needed.append(d)
            continue
        if d >= threshold_recent:
            if now - st.last_synced_at > timedelta(hours=24):
                needed.append(d)
    return needed

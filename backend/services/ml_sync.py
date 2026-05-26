"""Sincronização de cache ML por dia. Política de freshness."""
from datetime import date, datetime, timedelta


def _date_range(start: date, end: date) -> list[date]:
    """Lista inclusiva de datas entre start e end."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _days_needing_sync(days: list[date], statuses: dict[date, object]) -> list[date]:
    """Aplica política de freshness e retorna apenas os dias que precisam re-sync.

    Regras:
    - day == today → sempre.
    - day in [today-7, today-1] e last_synced_at > 24h → sim.
    - day < today-7 e status == 'ok' → não.
    - day < today-7 e status == 'failed' → sim.
    - day sem status → sim.
    """
    today = date.today()
    threshold_recent = today - timedelta(days=7)
    now = datetime.utcnow()
    needed = []
    for d in days:
        if d == today:
            needed.append(d)
            continue
        st = statuses.get(d)
        if st is None:
            needed.append(d)
            continue
        if st.status == "failed":
            needed.append(d)
            continue
        if d >= threshold_recent:
            if now - st.last_synced_at > timedelta(hours=24):
                needed.append(d)
    return needed

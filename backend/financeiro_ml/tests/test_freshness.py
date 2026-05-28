from datetime import date, datetime, timedelta
from financeiro_ml.freshness import days_needing_sync


class _St:
    def __init__(self, status, last, next_retry=None):
        self.status = status
        self.last_synced_at = last
        self.next_retry_at = next_retry


def test_missing_day_needs_sync():
    today = date.today()
    assert today in days_needing_sync([today], {})


def test_ok_today_fresh_under_5min_skipped():
    today = date.today()
    st = {today: _St("ok", datetime.utcnow() - timedelta(minutes=2))}
    assert today not in days_needing_sync([today], st)


def test_ok_old_day_skipped():
    old = date.today() - timedelta(days=30)
    st = {old: _St("ok", datetime.utcnow() - timedelta(days=20))}
    assert old not in days_needing_sync([old], st)


def test_rate_limited_before_retry_skipped():
    d = date.today() - timedelta(days=1)
    st = {d: _St("rate_limited", datetime.utcnow(), next_retry=datetime.utcnow() + timedelta(minutes=5))}
    assert d not in days_needing_sync([d], st)


def test_rate_limited_after_retry_needs_sync():
    d = date.today() - timedelta(days=1)
    st = {d: _St("rate_limited", datetime.utcnow(), next_retry=datetime.utcnow() - timedelta(minutes=1))}
    assert d in days_needing_sync([d], st)


def test_imported_unverified_needs_sync():
    d = date.today() - timedelta(days=3)
    st = {d: _St("imported_unverified", datetime.utcnow() - timedelta(days=1))}
    assert d in days_needing_sync([d], st)

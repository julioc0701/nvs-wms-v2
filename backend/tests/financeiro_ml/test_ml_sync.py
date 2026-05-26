import pytest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from services.ml_sync import _days_needing_sync, _date_range


def test_date_range_inclusive():
    days = _date_range(date(2026, 5, 1), date(2026, 5, 3))
    assert days == [date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)]


def test_today_always_needs_sync():
    today = date.today()
    statuses = {today: MagicMock(last_synced_at=datetime.utcnow() - timedelta(minutes=1), status="ok")}
    result = _days_needing_sync([today], statuses)
    assert result == [today]


def test_old_day_not_needed_if_ok():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="ok")}
    result = _days_needing_sync([old], statuses)
    assert result == []


def test_old_day_failed_needs_retry():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="failed")}
    result = _days_needing_sync([old], statuses)
    assert result == [old]


def test_recent_day_stale_24h_needs_sync():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=25), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == [recent]


def test_recent_day_fresh_skipped():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=5), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == []


def test_missing_day_needs_sync():
    target = date.today() - timedelta(days=2)
    result = _days_needing_sync([target], {})
    assert result == [target]

"""Pure monthly quota-window tests."""
from datetime import datetime, timezone

from services.quota_policy import quota_period


def test_quota_period_uses_utc_calendar_month():
    assert quota_period(datetime(2026, 9, 1, tzinfo=timezone.utc)) == "2026-09"
    assert quota_period(datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)) == "2026-09"
    assert quota_period(datetime(2026, 10, 1, tzinfo=timezone.utc)) == "2026-10"

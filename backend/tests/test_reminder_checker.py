"""Unit tests for the pure ``check_user`` reminder detection function.

Tests target the implementation at ``backend/reminder_checker.py``.
"""

from datetime import datetime, timedelta, timezone

import pytest

from reminder_checker import (
    Notification,
    NotificationType,
    check_user,
)


def _todo(
    *,
    todo_id: str = "t1",
    title: str = "Task",
    status: str = "pending",
    due_date: str | None = None,
    reminder_at: str | None = None,
) -> dict:
    return {
        "id": todo_id,
        "title": title,
        "status": status,
        "due_date": due_date,
        "reminder_at": reminder_at,
    }


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)


# 1
def test_no_todos_returns_empty(now):
    assert check_user([], now=now) == []


# 2
def test_reminder_in_future_does_not_fire(now):
    future = (now + timedelta(hours=1)).isoformat()
    assert check_user([_todo(reminder_at=future)], now=now) == []


# 3
def test_reminder_at_now_fires(now):
    out = check_user([_todo(reminder_at=now.isoformat())], now=now)
    assert len(out) == 1
    assert out[0].notification_type == NotificationType.REMINDER_DUE
    assert out[0].todo_id == "t1"


# 4
def test_reminder_in_past_fires(now):
    past = (now - timedelta(minutes=5)).isoformat()
    out = check_user([_todo(reminder_at=past)], now=now)
    assert [n.notification_type for n in out] == [NotificationType.REMINDER_DUE]


# 5
def test_done_todo_never_fires_reminder(now):
    past = (now - timedelta(hours=1)).isoformat()
    todo = _todo(reminder_at=past, status="done")
    assert check_user([todo], now=now) == []


# 6
def test_overdue_due_date_yesterday_fires(now):
    out = check_user([_todo(due_date="2026-05-23")], now=now)
    assert [n.notification_type for n in out] == [NotificationType.OVERDUE]


# 7
def test_done_todo_never_fires_overdue(now):
    todo = _todo(due_date="2026-05-01", status="done")
    assert check_user([todo], now=now) == []


# 8
def test_dedup_skips_already_notified_reminder(now):
    past = (now - timedelta(minutes=1)).isoformat()
    out = check_user(
        [_todo(reminder_at=past)],
        now=now,
        already_notified={f"t1:{NotificationType.REMINDER_DUE.value}"},
    )
    assert out == []


# 9
def test_dedup_skips_already_notified_overdue(now):
    out = check_user(
        [_todo(due_date="2026-05-23")],
        now=now,
        already_notified={f"t1:{NotificationType.OVERDUE.value}"},
    )
    assert out == []


# 10
def test_dedup_independent_per_kind(now):
    past = (now - timedelta(minutes=1)).isoformat()
    todo = _todo(reminder_at=past, due_date="2026-05-23")
    out = check_user(
        [todo],
        now=now,
        already_notified={f"t1:{NotificationType.REMINDER_DUE.value}"},
    )
    kinds = [n.notification_type for n in out]
    assert kinds == [NotificationType.OVERDUE]


# 11
def test_naive_reminder_normalized_when_now_is_aware(now):
    """The implementation normalizes naive reminder_at strings to UTC.

    Note: passing a naive ``now`` is not supported by the current
    implementation (it crashes on the tz-aware/naive comparison), so this
    test passes an aware ``now`` and a naive reminder string.
    """
    naive_reminder = "2026-05-24T11:00:00"  # naive, treated as UTC
    out = check_user([_todo(reminder_at=naive_reminder)], now=now)
    assert [n.notification_type for n in out] == [NotificationType.REMINDER_DUE]


# 12
def test_notification_serializes_to_dict(now):
    past = (now - timedelta(minutes=1)).isoformat()
    [n] = check_user([_todo(reminder_at=past)], now=now)
    assert isinstance(n, Notification)
    serialized = n.to_dict()
    assert serialized["todo_id"] == "t1"
    assert serialized["notification_type"] == "reminder_due"
    assert serialized["reminder_at"] == past

"""Notification persistence and delivery service.

This wraps the pure ``check_user`` detection function with a persistent
store so already-delivered notifications survive across requests and
process restarts. Each persisted notification is keyed by
``(user_id, todo_id, notification_type)``.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make the backend root importable so we can use the same flat-import style
# the rest of the project uses.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from exceptions import NotFoundError  # noqa: E402
from reminder_checker import NotificationType, check_user  # noqa: E402
from services import ai_service  # noqa: E402
from store import JSONStore  # noqa: E402

AI_COACH_TYPE = "ai_coach"
AI_COACH_INTERVAL = timedelta(hours=6)


class NotificationService:
    """Persists notifications and exposes user-facing list / mark / clear."""

    def __init__(self, notification_store: JSONStore, todo_store: JSONStore):
        self.notification_store = notification_store
        self.todo_store = todo_store

    # ------------------------------------------------------------------
    # Detection + persistence
    # ------------------------------------------------------------------
    def detect_for_user(
        self,
        user_id: str,
        now: datetime | None = None,
    ) -> list[dict]:
        """Run reminder detection for ``user_id`` and persist new notifications.

        Returns the list of newly persisted notification records (dicts).
        Already-delivered notifications are not re-emitted.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        user_todos = [
            t for t in self.todo_store.read_all() if t.get("user_id") == user_id
        ]

        existing = [
            n for n in self.notification_store.read_all() if n.get("user_id") == user_id
        ]
        already_notified = {
            f"{n['todo_id']}:{n['notification_type']}" for n in existing
        }

        candidates = check_user(user_todos, now=now, already_notified=already_notified)

        new_records: list[dict] = []
        for candidate in candidates:
            record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "todo_id": candidate.todo_id,
                "todo_title": candidate.todo_title,
                "notification_type": candidate.notification_type.value,
                "triggered_at": candidate.triggered_at.isoformat(),
                "delivered_at": now.isoformat(),
                "read": False,
            }
            self.notification_store.add(record)
            new_records.append(record)

        ai_notification = self._maybe_emit_ai_coach(user_id, user_todos, existing, now)
        if ai_notification:
            new_records.append(ai_notification)

        return new_records

    # ------------------------------------------------------------------
    # AI coach notification (rate-limited)
    # ------------------------------------------------------------------
    def _maybe_emit_ai_coach(
        self,
        user_id: str,
        user_todos: list[dict],
        existing: list[dict],
        now: datetime,
    ) -> dict | None:
        if not ai_service.is_enabled():
            return None
        if not [t for t in user_todos if t.get("status") != "done"]:
            return None

        # Throttle: don't emit if we already produced an AI nudge recently.
        latest = max(
            (
                _parse_iso(n.get("delivered_at"))
                for n in existing
                if n.get("notification_type") == AI_COACH_TYPE
            ),
            default=None,
        )
        if latest is not None and (now - latest) < AI_COACH_INTERVAL:
            return None

        # Folders are best-effort context — skip if unavailable.
        try:
            from routers.folders import folder_service

            folders = [
                f.model_dump() for f in folder_service.list_for_user(user_id)
            ]
        except Exception:
            folders = []

        message = ai_service.coach_message(todos=user_todos, folders=folders)
        if not message:
            return None

        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "todo_id": "",
            "todo_title": message,
            "notification_type": AI_COACH_TYPE,
            "triggered_at": now.isoformat(),
            "delivered_at": now.isoformat(),
            "read": False,
        }
        self.notification_store.add(record)
        return record

    # ------------------------------------------------------------------
    # User-facing reads
    # ------------------------------------------------------------------
    def list_for_user(
        self,
        user_id: str,
        unread_only: bool = False,
    ) -> list[dict]:
        """Return persisted notifications for ``user_id`` (newest first)."""
        records = [
            n for n in self.notification_store.read_all() if n.get("user_id") == user_id
        ]
        if unread_only:
            records = [n for n in records if not n.get("read", False)]
        records.sort(key=lambda n: n.get("delivered_at", ""), reverse=True)
        return records

    def unread_count(self, user_id: str) -> int:
        return sum(
            1
            for n in self.notification_store.read_all()
            if n.get("user_id") == user_id and not n.get("read", False)
        )

    # ------------------------------------------------------------------
    # User-facing mutations
    # ------------------------------------------------------------------
    def mark_read(self, user_id: str, notification_id: str) -> dict:
        record = self.notification_store.find_by_id(notification_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Notification not found")
        updated = self.notification_store.update(notification_id, {"read": True})
        if not updated:  # pragma: no cover - defensive
            raise NotFoundError("Notification not found")
        return updated

    def mark_all_read(self, user_id: str) -> int:
        records = self.notification_store.read_all()
        count = 0
        for n in records:
            if n.get("user_id") == user_id and not n.get("read", False):
                n["read"] = True
                count += 1
        if count:
            self.notification_store.write_all(records)
        return count

    def clear_all(self, user_id: str) -> int:
        """Permanently remove every notification for ``user_id``.

        Note: this also clears the dedup state, so the next ``detect_for_user``
        call may re-emit if the underlying conditions still hold. That matches
        the "Clear all" UX — the user wants a clean slate, not a permanent mute.
        """
        records = self.notification_store.read_all()
        kept = [n for n in records if n.get("user_id") != user_id]
        removed = len(records) - len(kept)
        if removed:
            self.notification_store.write_all(kept)
        return removed


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None

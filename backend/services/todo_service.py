"""Todo service handling CRUD operations scoped to authenticated users."""

import re
import uuid
from datetime import date, datetime, timezone

from exceptions import NotFoundError, ValidationError
from models import (
    Priority,
    Status,
    Subtask,
    Todo,
    TodoCreate,
    TodoStats,
    TodoUpdate,
)
from store import JSONStore


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip().lower()
        if not cleaned:
            continue
        if len(cleaned) > 32:
            cleaned = cleaned[:32]
        if cleaned not in seen:
            seen.append(cleaned)
    return seen


def _normalize_subtasks(subtasks: list[Subtask] | list[dict] | None) -> list[dict]:
    if not subtasks:
        return []
    out: list[dict] = []
    for entry in subtasks:
        if isinstance(entry, Subtask):
            out.append(entry.model_dump())
            continue
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "id": entry.get("id") or str(uuid.uuid4()),
                "title": title[:200],
                "done": bool(entry.get("done", False)),
            }
        )
    return out


class TodoService:
    """Handles CRUD operations on todos scoped to the authenticated user."""

    def __init__(self, todo_store: JSONStore):
        """Initialize with todo store.

        Args:
            todo_store: JSONStore instance for todo persistence.
        """
        self.todo_store = todo_store

    def create(self, user_id: str, data: TodoCreate) -> Todo:
        """Create a todo for the user.

        Validates title, sets defaults (priority=medium, status=pending),
        generates UUID, sets created_at, and persists to store.

        Args:
            user_id: The authenticated user's ID.
            data: TodoCreate model with todo fields.

        Returns:
            The created Todo object.

        Raises:
            ValidationError: If title is invalid or due_date format is wrong.
        """
        # Validate title is not whitespace-only
        if not data.title or not data.title.strip():
            raise ValidationError([{"field": "title", "message": "Title must not be blank"}])

        # Validate due_date format if provided
        if data.due_date is not None:
            self._validate_due_date(data.due_date)

        # Validate reminder_at format if provided
        reminder_at_value = None
        if data.reminder_at is not None:
            parsed_reminder = self._validate_reminder_at(data.reminder_at)
            reminder_at_value = parsed_reminder.isoformat()

        # Create todo record with defaults
        existing_records = self.todo_store.read_all()
        max_position = max(
            (r.get("position", 0) for r in existing_records if r.get("user_id") == user_id),
            default=-1,
        )
        todo_data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": data.title,
            "description": data.description,
            "priority": data.priority.value if data.priority else Priority.MEDIUM.value,
            "due_date": data.due_date,
            "reminder_at": reminder_at_value,
            "status": data.status.value if data.status else Status.PENDING.value,
            "folder_id": data.folder_id,
            "tags": _normalize_tags(data.tags),
            "subtasks": _normalize_subtasks(data.subtasks),
            "image_url": None,
            "position": max_position + 1,
            "time_spent_seconds": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }

        self.todo_store.add(todo_data)

        return Todo(**todo_data)

    def list_todos(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        sort_by: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        folder_id: str | None = None,
    ) -> list[Todo]:
        """List user's todos with optional filtering and sorting.

        Filters by user_id, applies optional status/priority/tag/search/folder
        filters, and applies sort (due_date asc with nulls last, created_at
        desc, or manual ``position`` order).
        """
        # Validate filter values
        if status is not None:
            valid_statuses = [s.value for s in Status]
            if status not in valid_statuses:
                raise ValidationError(
                    [{"field": "status", "message": f"Invalid status value. Must be one of: {', '.join(valid_statuses)}"}]
                )

        if priority is not None:
            valid_priorities = [p.value for p in Priority]
            if priority not in valid_priorities:
                raise ValidationError(
                    [{"field": "priority", "message": f"Invalid priority value. Must be one of: {', '.join(valid_priorities)}"}]
                )

        if sort_by is not None:
            valid_sorts = ["due_date", "created_at", "position"]
            if sort_by not in valid_sorts:
                raise ValidationError(
                    [{"field": "sort_by", "message": f"Invalid sort_by value. Must be one of: {', '.join(valid_sorts)}"}]
                )

        # Get all records and filter by user_id
        all_records = self.todo_store.read_all()
        user_todos = [r for r in all_records if r.get("user_id") == user_id]

        # Apply status filter
        if status is not None:
            user_todos = [r for r in user_todos if r.get("status") == status]

        # Apply priority filter
        if priority is not None:
            user_todos = [r for r in user_todos if r.get("priority") == priority]

        # Apply tag filter (case-insensitive exact match)
        if tag is not None:
            tag_lower = tag.strip().lower()
            if tag_lower:
                user_todos = [r for r in user_todos if tag_lower in (r.get("tags") or [])]

        # Apply folder filter ("none" matches todos with no folder)
        if folder_id is not None:
            if folder_id == "none":
                user_todos = [r for r in user_todos if not r.get("folder_id")]
            else:
                user_todos = [r for r in user_todos if r.get("folder_id") == folder_id]

        # Apply free-text search across title + description + tags
        if search is not None:
            needle = search.strip().lower()
            if needle:
                def _matches(record: dict) -> bool:
                    title = (record.get("title") or "").lower()
                    description = (record.get("description") or "").lower()
                    tags = " ".join(record.get("tags") or []).lower()
                    return needle in title or needle in description or needle in tags

                user_todos = [r for r in user_todos if _matches(r)]

        # Apply sorting
        if sort_by == "due_date":
            user_todos.sort(key=lambda r: (r.get("due_date") is None, r.get("due_date") or ""))
        elif sort_by == "created_at":
            user_todos.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        elif sort_by == "position":
            user_todos.sort(key=lambda r: (r.get("position", 0), r.get("created_at", "")))

        return [Todo(**r) for r in user_todos]

    def get_by_id(self, user_id: str, todo_id: str) -> Todo:
        """Get a specific todo by ID.

        Finds the todo and verifies ownership. Returns 404 if not found or not owned.

        Args:
            user_id: The authenticated user's ID.
            todo_id: The todo's ID to retrieve.

        Returns:
            The Todo object.

        Raises:
            NotFoundError: If todo is not found or not owned by user.
        """
        record = self.todo_store.find_by_id(todo_id)

        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        return Todo(**record)

    def update(self, user_id: str, todo_id: str, data: TodoUpdate) -> Todo:
        """Update a todo.

        Finds the todo, verifies ownership, updates only provided fields,
        and sets updated_at.

        Args:
            user_id: The authenticated user's ID.
            todo_id: The todo's ID to update.
            data: TodoUpdate model with fields to update.

        Returns:
            The updated Todo object.

        Raises:
            NotFoundError: If todo is not found or not owned by user.
            ValidationError: If updated fields are invalid.
        """
        # Find and verify ownership
        record = self.todo_store.find_by_id(todo_id)

        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        # Build updates dict with only provided fields
        updates = {}

        if data.title is not None:
            if not data.title.strip():
                raise ValidationError([{"field": "title", "message": "Title must not be blank"}])
            updates["title"] = data.title

        if data.description is not None:
            updates["description"] = data.description

        if data.priority is not None:
            updates["priority"] = data.priority.value

        if data.due_date is not None:
            self._validate_due_date(data.due_date)
            updates["due_date"] = data.due_date

        if data.reminder_at is not None:
            if data.reminder_at == "":
                # Explicit empty string clears the reminder
                updates["reminder_at"] = None
            else:
                parsed_reminder = self._validate_reminder_at(data.reminder_at)
                updates["reminder_at"] = parsed_reminder.isoformat()

        if data.status is not None:
            updates["status"] = data.status.value

        if data.tags is not None:
            updates["tags"] = _normalize_tags(data.tags)

        if data.subtasks is not None:
            updates["subtasks"] = _normalize_subtasks(data.subtasks)

        if data.folder_id is not None:
            # Empty string clears the folder assignment
            updates["folder_id"] = data.folder_id or None

        if data.position is not None:
            updates["position"] = int(data.position)

        # Set updated_at timestamp
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Persist updates
        updated_record = self.todo_store.update(todo_id, updates)

        if not updated_record:
            raise NotFoundError("Todo not found")

        return Todo(**updated_record)

    def delete(self, user_id: str, todo_id: str) -> None:
        """Delete a todo.

        Finds the todo, verifies ownership, and removes from store.

        Args:
            user_id: The authenticated user's ID.
            todo_id: The todo's ID to delete.

        Raises:
            NotFoundError: If todo is not found or not owned by user.
        """
        # Find and verify ownership
        record = self.todo_store.find_by_id(todo_id)

        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        # Remove from store
        deleted = self.todo_store.delete(todo_id)

        if not deleted:
            raise NotFoundError("Todo not found")

    def reorder(self, user_id: str, ordered_ids: list[str]) -> list[Todo]:
        """Persist a manual ordering for the given todo ids.

        Each id in ``ordered_ids`` must belong to ``user_id``; ids not in the
        list keep their existing position. Returns the user's todos in the new
        order.
        """
        records = self.todo_store.read_all()
        owned_ids = {r["id"] for r in records if r.get("user_id") == user_id}
        unknown = [tid for tid in ordered_ids if tid not in owned_ids]
        if unknown:
            raise NotFoundError("One or more todos not found")

        rank = {tid: idx for idx, tid in enumerate(ordered_ids)}
        for r in records:
            if r["id"] in rank:
                r["position"] = rank[r["id"]]
        self.todo_store.write_all(records)
        return self.list_todos(user_id=user_id, sort_by="position")

    def add_time(self, user_id: str, todo_id: str, seconds: int) -> Todo:
        """Add ``seconds`` to a todo's ``time_spent_seconds`` (Pomodoro)."""
        if seconds < 0:
            raise ValidationError([{"field": "seconds", "message": "seconds must be >= 0"}])
        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")
        new_total = int(record.get("time_spent_seconds") or 0) + int(seconds)
        updated = self.todo_store.update(
            todo_id,
            {
                "time_spent_seconds": new_total,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return Todo(**updated)

    def set_image(self, user_id: str, todo_id: str, image_url: str | None) -> Todo:
        """Attach (or detach) an image URL to a todo."""
        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")
        updated = self.todo_store.update(
            todo_id,
            {
                "image_url": image_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return Todo(**updated)

    def list_tags(self, user_id: str) -> list[dict]:
        """Return distinct tags used by the user with usage counts."""
        records = [r for r in self.todo_store.read_all() if r.get("user_id") == user_id]
        counts: dict[str, int] = {}
        for r in records:
            for tag in r.get("tags") or []:
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]


        """Compute dashboard statistics for the user.

        Computes total, completed, pending, and overdue counts.
        Overdue = due_date before today AND status != done.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            TodoStats with computed counts.
        """
        all_records = self.todo_store.read_all()
        user_todos = [r for r in all_records if r.get("user_id") == user_id]

        total = len(user_todos)
        completed = sum(1 for r in user_todos if r.get("status") == Status.DONE.value)
        pending = sum(1 for r in user_todos if r.get("status") in (Status.PENDING.value, Status.IN_PROGRESS.value))

        today = date.today()
        overdue = 0
        for r in user_todos:
            due = r.get("due_date")
            if due and r.get("status") != Status.DONE.value:
                try:
                    due_date = date.fromisoformat(due)
                    if due_date < today:
                        overdue += 1
                except (ValueError, TypeError):
                    pass

        return TodoStats(total=total, completed=completed, pending=pending, overdue=overdue)

    def _validate_due_date(self, due_date: str) -> None:
        """Validate that due_date is a valid ISO 8601 date (YYYY-MM-DD).

        Args:
            due_date: The date string to validate.

        Raises:
            ValidationError: If the date format is invalid.
        """
        # Check format with regex first
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", due_date):
            raise ValidationError(
                [{"field": "due_date", "message": "Invalid date format. Must be YYYY-MM-DD"}]
            )

        # Verify it's a valid date
        try:
            date.fromisoformat(due_date)
        except ValueError:
            raise ValidationError(
                [{"field": "due_date", "message": "Invalid date format. Must be YYYY-MM-DD"}]
            )

    def _validate_reminder_at(self, reminder_at: str) -> datetime:
        """Validate that reminder_at is a valid ISO 8601 datetime string.

        Args:
            reminder_at: The datetime string to validate.

        Returns:
            The parsed datetime object.

        Raises:
            ValidationError: If the datetime format is invalid.
        """
        try:
            parsed = datetime.fromisoformat(reminder_at)
            return parsed
        except (ValueError, TypeError):
            raise ValidationError(
                [{"field": "reminder_at", "message": "Invalid datetime format. Must be ISO 8601 (e.g. 2025-01-15T09:00:00)"}]
            )

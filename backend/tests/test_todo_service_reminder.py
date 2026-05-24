"""Unit tests for ``TodoService`` ``reminder_at`` create/update behavior.

Tests target the implementation that lives on ``main`` (the collaborator's
Unit 2 commit), where the update semantics use an empty string ``""`` to
clear the reminder rather than an explicit ``null``.
"""

from pathlib import Path

import pytest

from exceptions import ValidationError
from models import TodoCreate, TodoUpdate
from services.todo_service import TodoService
from store import JSONStore


@pytest.fixture
def todo_service(tmp_path: Path) -> TodoService:
    todos_file = tmp_path / "todos.json"
    todos_file.write_text("[]")
    return TodoService(JSONStore(str(todos_file)))


# 13
def test_create_persists_reminder_at(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="Pay invoice", reminder_at="2026-12-01T09:00:00+00:00"),
    )
    assert todo.reminder_at is not None
    assert todo.reminder_at.year == 2026
    assert todo.reminder_at.month == 12


# 14
def test_create_invalid_reminder_at_raises_422(todo_service):
    with pytest.raises(ValidationError):
        todo_service.create(
            "u1",
            TodoCreate(title="Bad", reminder_at="not-a-date"),
        )


# 15
def test_create_accepts_naive_iso(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="Naive", reminder_at="2026-06-15T08:00:00"),
    )
    assert todo.reminder_at is not None


# 16
def test_create_accepts_offset_format(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="Offset", reminder_at="2026-06-15T08:00:00+02:00"),
    )
    assert todo.reminder_at is not None


# 17
def test_update_changes_reminder_at(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="Initial", reminder_at="2026-06-01T08:00:00+00:00"),
    )
    updated = todo_service.update(
        "u1",
        todo.id,
        TodoUpdate(reminder_at="2027-01-15T12:00:00+02:00"),
    )
    assert updated.reminder_at is not None
    assert updated.reminder_at.year == 2027


# 18 — empty string clears the reminder
def test_update_with_empty_string_clears_reminder_at(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="To clear", reminder_at="2026-06-01T08:00:00+00:00"),
    )
    updated = todo_service.update("u1", todo.id, TodoUpdate(reminder_at=""))
    assert updated.reminder_at is None


# 19
def test_update_without_field_preserves_reminder_at(todo_service):
    todo = todo_service.create(
        "u1",
        TodoCreate(title="Keep me", reminder_at="2026-06-01T08:00:00+00:00"),
    )
    updated = todo_service.update("u1", todo.id, TodoUpdate(title="Renamed"))
    assert updated.reminder_at is not None
    assert updated.reminder_at.year == 2026


# 20
def test_update_invalid_reminder_at_raises_422(todo_service):
    todo = todo_service.create("u1", TodoCreate(title="Anchor"))
    with pytest.raises(ValidationError):
        todo_service.update("u1", todo.id, TodoUpdate(reminder_at="garbage"))

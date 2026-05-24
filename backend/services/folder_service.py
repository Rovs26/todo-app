"""Folder (category) service.

Folders are user-owned containers for todos. A todo references its folder by
``folder_id`` (nullable). Deleting a folder detaches its todos rather than
deleting them — the user's data is preserved.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from exceptions import ConflictError, NotFoundError, ValidationError  # noqa: E402
from models import Folder, FolderCreate, FolderUpdate  # noqa: E402
from store import JSONStore  # noqa: E402


class FolderService:
    """CRUD for user-owned folders, with todo-detach on delete."""

    def __init__(self, folder_store: JSONStore, todo_store: JSONStore):
        self.folder_store = folder_store
        self.todo_store = todo_store

    # ------------------------------------------------------------------
    def list_for_user(self, user_id: str) -> list[Folder]:
        records = [
            r for r in self.folder_store.read_all() if r.get("user_id") == user_id
        ]
        records.sort(key=lambda r: (r.get("name") or "").lower())
        return [Folder(**r) for r in records]

    def get(self, user_id: str, folder_id: str) -> Folder:
        record = self.folder_store.find_by_id(folder_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Folder not found")
        return Folder(**record)

    def create(self, user_id: str, data: FolderCreate) -> Folder:
        name = (data.name or "").strip()
        if not name:
            raise ValidationError([{"field": "name", "message": "Name must not be blank"}])

        # Enforce per-user uniqueness on name (case-insensitive)
        existing = self.list_for_user(user_id)
        if any(f.name.lower() == name.lower() for f in existing):
            raise ConflictError("Folder with this name already exists")

        record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name[:80],
            "color": data.color,
            "icon": data.icon,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        self.folder_store.add(record)
        return Folder(**record)

    def update(self, user_id: str, folder_id: str, data: FolderUpdate) -> Folder:
        record = self.folder_store.find_by_id(folder_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Folder not found")

        updates: dict = {}
        if data.name is not None:
            new_name = data.name.strip()
            if not new_name:
                raise ValidationError([{"field": "name", "message": "Name must not be blank"}])
            # Uniqueness check excluding this folder
            for f in self.list_for_user(user_id):
                if f.id != folder_id and f.name.lower() == new_name.lower():
                    raise ConflictError("Folder with this name already exists")
            updates["name"] = new_name[:80]
        if data.color is not None:
            updates["color"] = data.color or None
        if data.icon is not None:
            updates["icon"] = data.icon or None
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated = self.folder_store.update(folder_id, updates)
        return Folder(**updated)

    def delete(self, user_id: str, folder_id: str) -> None:
        """Delete a folder. Todos that referenced it have ``folder_id`` cleared."""
        record = self.folder_store.find_by_id(folder_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Folder not found")

        # Detach todos in this folder before deleting it
        todos = self.todo_store.read_all()
        changed = False
        for t in todos:
            if t.get("user_id") == user_id and t.get("folder_id") == folder_id:
                t["folder_id"] = None
                t["updated_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
        if changed:
            self.todo_store.write_all(todos)

        self.folder_store.delete(folder_id)

    def folder_stats(self, user_id: str) -> list[dict]:
        """Return folder summaries with per-folder counts."""
        folders = self.list_for_user(user_id)
        todos = [t for t in self.todo_store.read_all() if t.get("user_id") == user_id]

        out: list[dict] = []
        for f in folders:
            in_folder = [t for t in todos if t.get("folder_id") == f.id]
            done = sum(1 for t in in_folder if t.get("status") == "done")
            out.append(
                {
                    "id": f.id,
                    "name": f.name,
                    "color": f.color,
                    "icon": f.icon,
                    "total": len(in_folder),
                    "completed": done,
                    "pending": len(in_folder) - done,
                }
            )
        # Add a synthetic "no folder" bucket
        unassigned = [t for t in todos if not t.get("folder_id")]
        if unassigned:
            done = sum(1 for t in unassigned if t.get("status") == "done")
            out.append(
                {
                    "id": "none",
                    "name": "Unassigned",
                    "color": None,
                    "icon": None,
                    "total": len(unassigned),
                    "completed": done,
                    "pending": len(unassigned) - done,
                }
            )
        return out

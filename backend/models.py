"""Pydantic data models for the Todo application."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# --- User Models ---


class User(BaseModel):
    """Internal user model with all fields including password hash."""

    id: str  # UUID4 string
    email: EmailStr  # Valid email format
    username: str  # 3-30 chars, alphanumeric + underscore
    password_hash: str  # bcrypt hash
    created_at: datetime  # ISO 8601 timestamp


class UserCreate(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8)
    password_confirm: str


class UserResponse(BaseModel):
    """Response model for user data (excludes password_hash)."""

    id: str
    email: str
    username: str
    created_at: datetime


# --- Enums ---


class Priority(str, Enum):
    """Priority levels for todo items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(str, Enum):
    """Status values for todo items."""

    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    DONE = "done"


# --- Todo Models ---


class Subtask(BaseModel):
    """A single sub-item on a todo (used for checklists)."""

    id: str
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class Todo(BaseModel):
    """Internal todo model with all fields."""

    id: str  # UUID4 string
    user_id: str  # Reference to User.id
    title: str  # 1-200 chars, non-whitespace-only
    description: str | None = None  # Optional, max 2000 chars
    priority: Priority = Priority.MEDIUM
    due_date: str | None = None  # ISO 8601 date (YYYY-MM-DD) or None
    reminder_at: datetime | None = None  # ISO 8601 datetime for reminder trigger
    status: Status = Status.PENDING
    folder_id: str | None = None  # Optional grouping under a Folder
    tags: list[str] = Field(default_factory=list)  # User-defined labels
    subtasks: list[Subtask] = Field(default_factory=list)
    image_url: str | None = None  # Server-relative URL (set by upload endpoint)
    position: int = 0  # User-defined ordering (lower first)
    time_spent_seconds: int = 0  # Pomodoro / focus time accumulator
    created_at: datetime
    updated_at: datetime | None = None


class TodoCreate(BaseModel):
    """Request model for creating a todo."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority = Priority.MEDIUM
    due_date: str | None = None  # Validated as YYYY-MM-DD
    reminder_at: str | None = None  # ISO 8601 datetime string
    status: Status = Status.PENDING
    folder_id: str | None = None
    tags: list[str] | None = None
    subtasks: list[Subtask] | None = None


class TodoUpdate(BaseModel):
    """Request model for updating a todo (all fields optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    due_date: str | None = None
    reminder_at: str | None = None  # ISO 8601 datetime string, explicit null clears
    status: Status | None = None
    folder_id: str | None = None  # Empty string clears the folder assignment
    tags: list[str] | None = None
    subtasks: list[Subtask] | None = None
    position: int | None = None


class TodoStats(BaseModel):
    """Statistics model for dashboard display."""

    total: int
    completed: int
    pending: int
    overdue: int


# --- Folder Models ---


class Folder(BaseModel):
    """A folder / category that groups related todos for one user."""

    id: str
    user_id: str
    name: str = Field(min_length=1, max_length=80)
    color: str | None = None  # Free-form hex like #6366F1
    icon: str | None = None  # Optional emoji or short label
    created_at: datetime
    updated_at: datetime | None = None


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = None
    icon: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = None
    icon: str | None = None

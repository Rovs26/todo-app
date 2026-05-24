"""AI helpers powered by OpenAI when an API key is configured.

The service is intentionally tolerant: when no key is present, calls return a
deterministic local fallback so the app remains fully usable.

The API key is read from ``OPENAI_API_KEY`` (loaded from .env or .env.local
via python-dotenv at process startup).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

try:  # python-dotenv is optional in tests
    from dotenv import load_dotenv
    from pathlib import Path

    # Look for .env files starting at the repo root (parent of backend/) so
    # the same .env.local works regardless of which directory uvicorn was
    # launched from.
    _here = Path(__file__).resolve()
    _candidates = [
        _here.parents[2] / ".env",       # repo root .env
        _here.parents[2] / ".env.local", # repo root .env.local (overrides)
        _here.parents[1] / ".env",       # backend/.env
        _here.parents[1] / ".env.local", # backend/.env.local
    ]
    for _path in _candidates:
        if _path.exists():
            load_dotenv(_path, override=True)
except Exception:  # pragma: no cover
    pass

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


def _client() -> Any | None:
    if not is_enabled():
        return None
    try:
        return OpenAI()
    except Exception:
        return None


def _todo_brief(todo: dict) -> dict:
    """Reduce a todo to the small set of fields we send to the model."""
    return {
        "title": todo.get("title"),
        "status": todo.get("status"),
        "priority": todo.get("priority"),
        "due_date": todo.get("due_date"),
        "tags": todo.get("tags") or [],
        "folder_id": todo.get("folder_id"),
    }


def smart_summary(
    *,
    todos: list[dict],
    folders: list[dict],
    fallback: str,
) -> dict:
    """Generate a natural-language summary of the user's todos.

    Falls back to ``fallback`` (the deterministic summary) when no OpenAI key
    is configured or the call fails.
    """
    client = _client()
    if not client:
        return {"summary": fallback, "source": "local"}

    payload = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [{"id": f.get("id"), "name": f.get("name")} for f in folders],
        "todos": [_todo_brief(t) for t in todos[:80]],
    }

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise productivity coach. Given the user's "
                        "todos, write a 2-4 sentence summary that calls out the "
                        "most urgent or impactful next steps. Mention specific "
                        "todo titles when helpful. No bullet lists, no headings, "
                        "no questions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0.4,
            max_tokens=180,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return {"summary": fallback, "source": "local"}
        return {"summary": text, "source": "openai"}
    except Exception as exc:  # pragma: no cover - network / quota issues
        return {
            "summary": fallback,
            "source": "local",
            "error": str(exc),
        }


def suggest_subtasks(*, title: str, description: str | None) -> list[str]:
    """Ask the model to break a todo into 3-5 actionable subtasks."""
    client = _client()
    if not client:
        return []

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert a user task into 3 to 5 short, concrete, "
                        "ordered subtasks. Reply ONLY with a JSON array of "
                        "strings. No prose, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"title": title, "description": description or ""},
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=200,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            # remove leading "json\n" if any
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:5]
        return []
    except Exception:  # pragma: no cover
        return []


def coach_message(
    *,
    todos: list[dict],
    folders: list[dict],
) -> str | None:
    """Generate a short proactive nudge for the user.

    Used by the "AI notifications" feature. Returns ``None`` when no nudge is
    appropriate or when the API is unavailable.
    """
    client = _client()
    if not client:
        return None

    pending = [t for t in todos if t.get("status") != "done"]
    if not pending:
        return None

    payload = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [{"id": f.get("id"), "name": f.get("name")} for f in folders],
        "todos": [_todo_brief(t) for t in pending[:60]],
    }

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly, brief productivity coach. Look at "
                        "the user's open todos and surface ONE actionable nudge "
                        "in a single short sentence. Mention specific titles "
                        "when helpful. Plain text, no markdown, no questions."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.5,
            max_tokens=80,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None


def transcribe_audio(file_bytes: bytes, filename: str) -> str | None:
    """Transcribe audio bytes via Whisper. Returns ``None`` on failure."""
    client = _client()
    if not client:
        return None
    try:
        # The OpenAI SDK accepts a (filename, bytes) tuple as the file argument.
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename or "audio.webm", file_bytes),
        )
        text = (getattr(result, "text", "") or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None


def chat(
    *,
    user_message: str,
    history: list[dict],
    todos: list[dict],
    folders: list[dict],
) -> str | None:
    """Conversational assistant grounded in the user's todos.

    ``history`` is a list of ``{"role": "user"|"assistant", "content": str}``
    entries representing prior turns of the same conversation. Returns
    ``None`` when AI is unavailable.
    """
    client = _client()
    if not client:
        return None

    context = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [
            {"id": f.get("id"), "name": f.get("name")} for f in folders
        ],
        "todos": [
            dict(_todo_brief(t), id=t.get("id")) for t in todos[:80]
        ],
    }

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a concise, helpful assistant inside a personal todo "
                "app. The user's current todos and folders are provided as "
                "JSON in the next message. Use that context when answering. "
                "Keep replies short (2-4 sentences). Reference todos by their "
                "title in quotes when useful. No markdown headings."
            ),
        },
        {
            "role": "system",
            "content": "USER_CONTEXT_JSON: " + json.dumps(context, ensure_ascii=False),
        },
    ]
    for turn in history[-10:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None

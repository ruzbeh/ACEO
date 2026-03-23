"""Bridge company JSON logs into the active initiative run (avoids circular imports)."""
from __future__ import annotations

from typing import Any, Callable

_append_fn: Callable[[str, dict[str, Any]], None] | None = None


def register_initiative_live_append(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    """Set by routes_initiatives at import time; cleared in tests if needed."""
    global _append_fn
    _append_fn = fn


def append_initiative_live_line(initiative_id: str, line: dict[str, Any]) -> None:
    if _append_fn:
        _append_fn(initiative_id, line)

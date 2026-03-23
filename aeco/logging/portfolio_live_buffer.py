"""Bridge company JSON logs into the active portfolio run (avoids circular imports)."""
from __future__ import annotations

from typing import Any, Callable

_append_fn: Callable[[str, dict[str, Any]], None] | None = None


def register_portfolio_live_append(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    """Set by routes_portfolio at import time; cleared in tests if needed."""
    global _append_fn
    _append_fn = fn


def append_portfolio_live_line(portfolio_id: str, line: dict[str, Any]) -> None:
    if _append_fn:
        _append_fn(portfolio_id, line)

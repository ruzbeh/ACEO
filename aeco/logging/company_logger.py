"""
Structured logging for observing the company (workflow, agents, tools) in action.

Logs are emitted as one JSON object per line for easy parsing and tail -f.
Categories: workflow | agent | tool | state | error
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Set for the duration of an async portfolio workflow so all company_log lines
# (agents, tools, nodes) are attributed to that portfolio run.
portfolio_run_id: ContextVar[str | None] = ContextVar("portfolio_run_id", default=None)

# Set during initiative graph execution so agent/tool/node logs stream to initiative live log.
initiative_run_id: ContextVar[str | None] = ContextVar("initiative_run_id", default=None)

# Module-level logger; configured by init_company_logging()
_company_logger: logging.Logger | None = None
_company_handler: logging.Handler | None = None


def _serialize(obj: Any) -> Any:
    """Make payload JSON-serializable."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return str(obj)


def _emit(category: str, event: str, **payload: Any) -> None:
    """Emit one structured log line."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "cat": category,
        "event": event,
        **_serialize(payload),
    }
    pid = portfolio_run_id.get() or payload.get("portfolio_id")
    if pid:
        from aeco.logging.portfolio_live_buffer import append_portfolio_live_line

        append_portfolio_live_line(pid, record)

    iid = initiative_run_id.get() or payload.get("initiative_id")
    if iid:
        from aeco.logging.initiative_live_buffer import append_initiative_live_line

        append_initiative_live_line(str(iid), record)

    if _company_logger is None or not _company_logger.handlers:
        return
    msg = json.dumps(record, default=str)
    _company_logger.log(logging.INFO, msg)


def company_log(category: str, event: str, **payload: Any) -> None:
    """Emit a company log entry (workflow | agent | tool | state | error)."""
    _emit(category, event, **payload)


def log_initiative_node(node: str, summary: str = "", initiative_id: str | None = None) -> None:
    """Structured step line for the initiative graph (shows in live trace)."""
    iid = initiative_id or initiative_run_id.get()
    if not iid:
        return
    company_log(
        "state",
        "initiative_node",
        initiative_id=iid,
        node=node,
        summary=summary[:500],
    )


# --- Workflow ---


def log_workflow_start(
    run_id: str,
    task_id: str,
    task_title: str,
    workspace_path: str,
) -> None:
    company_log(
        "workflow",
        "workflow_started",
        run_id=run_id,
        task_id=task_id,
        task_title=task_title,
        workspace_path=workspace_path,
    )


def log_workflow_completed(
    run_id: str,
    task_id: str,
    status: str,
    iterations: int,
    files_created: int,
) -> None:
    company_log(
        "workflow",
        "workflow_completed",
        run_id=run_id,
        task_id=task_id,
        status=status,
        iterations=iterations,
        files_created=files_created,
    )


def log_workflow_failed(run_id: str, task_id: str, error: str) -> None:
    company_log("workflow", "workflow_failed", run_id=run_id, task_id=task_id, error=error)


# --- Node (orchestrator step) ---


def log_node_enter(
    node: str,
    run_id: str | None,
    task_id: str | None,
    task_title: str,
    iteration: int | None = None,
    **extra: Any,
) -> None:
    company_log(
        "state",
        "node_enter",
        node=node,
        run_id=run_id,
        task_id=task_id,
        task_title=task_title[:200] if task_title else "",
        iteration=iteration,
        **extra,
    )


def log_node_exit(
    node: str,
    run_id: str | None,
    task_id: str | None,
    next_action: str | None = None,
    **extra: Any,
) -> None:
    company_log(
        "state",
        "node_exit",
        node=node,
        run_id=run_id,
        task_id=task_id,
        next_action=next_action,
        **extra,
    )


def log_route_decision(
    run_id: str | None,
    task_id: str | None,
    next_action: str,
    iteration: int,
    reasoning: str = "",
    forced: bool = False,
) -> None:
    company_log(
        "state",
        "route_decision",
        run_id=run_id,
        task_id=task_id,
        next_action=next_action,
        iteration=iteration,
        reasoning=reasoning[:500] if reasoning else "",
        forced=forced,
    )


# --- Agent ---


def log_agent_start(
    agent_id: str,
    task_id: str | None,
    run_id: str | None,
    context_keys: list[str] | None = None,
) -> None:
    company_log(
        "agent",
        "agent_start",
        agent_id=agent_id,
        task_id=task_id,
        run_id=run_id,
        context_keys=context_keys or [],
    )


def log_agent_end(
    agent_id: str,
    task_id: str | None,
    run_id: str | None,
    duration_ms: int,
    success: bool = True,
    tokens_used: int | None = None,
    output_summary: str | None = None,
    error: str | None = None,
) -> None:
    company_log(
        "agent",
        "agent_end",
        agent_id=agent_id,
        task_id=task_id,
        run_id=run_id,
        duration_ms=duration_ms,
        success=success,
        tokens_used=tokens_used,
        output_summary=(output_summary[:300] if output_summary else None),
        error=error,
    )


def log_agent_tool_round(
    agent_id: str,
    task_id: str | None,
    run_id: str | None,
    tool_name: str,
    round_index: int,
    success: bool = True,
    error: str | None = None,
) -> None:
    company_log(
        "tool",
        "tool_call",
        agent_id=agent_id,
        task_id=task_id,
        run_id=run_id,
        tool_name=tool_name,
        round_index=round_index,
        success=success,
        error=error,
    )


def log_agent_parse_result(
    agent_id: str,
    parse_ok: bool,
    raw_length: int,
    used_fallback: bool = False,
    task_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Baseline metric: whether agent output parsed as JSON. Enables parse-error rate tracking."""
    company_log(
        "agent",
        "parse_result",
        agent_id=agent_id,
        parse_ok=parse_ok,
        raw_length=raw_length,
        used_fallback=used_fallback,
        task_id=task_id,
        run_id=run_id,
    )


def get_company_logger() -> logging.Logger:
    """Return the company logger (for direct use if needed)."""
    global _company_logger
    if _company_logger is None:
        _company_logger = logging.getLogger("aeco.company")
    return _company_logger


def init_company_logging(
    log_path: str | Path | None = None,
    console: bool = True,
    level: int = logging.INFO,
) -> None:
    """
    Initialize company logging. Call once from main.py.

    - log_path: if set, append JSON lines to this file (e.g. logs/company.log).
    - console: if True, also emit company logs to stderr.
    """
    global _company_logger

    _company_logger = logging.getLogger("aeco.company")
    _company_logger.setLevel(level)
    _company_logger.propagate = False

    # Remove any existing handlers we added earlier (e.g. re-init)
    for h in list(_company_logger.handlers):
        _company_logger.removeHandler(h)

    formatter = logging.Formatter("%(message)s")  # message is already JSON

    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        _company_logger.addHandler(fh)

    if console:
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(level)
        # Human-readable one-liner for console (JSON still goes to file if log_path set)
        ch.setFormatter(
            logging.Formatter("%(asctime)s [company] %(message)s", datefmt="%H:%M:%S")
        )
        _company_logger.addHandler(ch)

    _company_logger.info(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "cat": "workflow",
                "event": "company_logging_started",
                "log_path": str(log_path) if log_path else None,
                "console": console,
            },
            default=str,
        )
    )

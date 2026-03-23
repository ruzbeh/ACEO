"""Metrics and agent logs tools for analytics and evaluation agents."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import async_session_factory
from aeco.models.audit import AuditLogEntry

logger = logging.getLogger(__name__)


async def metrics_read(
    metric_type: str = "agent_performance",
    agent_id: str | None = None,
    workflow_run_id: str | None = None,
    limit: int = 50,
) -> dict:
    """Read system metrics: agent performance, workflow stats, cost data.

    Args:
        metric_type: One of "agent_performance", "workflow_stats", "cost_summary", "error_rates".
        agent_id: Filter by specific agent (optional).
        workflow_run_id: Filter by specific workflow run (optional).
        limit: Max records to return.

    Returns:
        Metrics data with aggregations and breakdowns.
    """
    async with async_session_factory() as session:
        if metric_type == "agent_performance":
            return await _agent_performance(session, agent_id, limit)
        elif metric_type == "workflow_stats":
            return await _workflow_stats(session, workflow_run_id, limit)
        elif metric_type == "cost_summary":
            return await _cost_summary(session, agent_id, limit)
        elif metric_type == "error_rates":
            return await _error_rates(session, agent_id, limit)
        else:
            return {"error": f"Unknown metric_type: {metric_type}"}


async def agent_logs_read(
    agent_id: str | None = None,
    action: str | None = None,
    success: bool | None = None,
    limit: int = 50,
) -> dict:
    """Read agent execution logs from the audit trail.

    Args:
        agent_id: Filter by agent (optional).
        action: Filter by action type, e.g. "llm_call" (optional).
        success: Filter by success/failure (optional).
        limit: Max records to return.

    Returns:
        List of audit log entries with token usage, duration, and outcomes.
    """
    async with async_session_factory() as session:
        stmt = select(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc())

        if agent_id:
            stmt = stmt.where(AuditLogEntry.agent_id == agent_id)
        if action:
            stmt = stmt.where(AuditLogEntry.action == action)
        if success is not None:
            stmt = stmt.where(AuditLogEntry.success.is_(success))

        stmt = stmt.limit(limit)
        result = await session.execute(stmt)

        entries = []
        for entry in result.scalars():
            entries.append({
                "id": str(entry.id),
                "timestamp": entry.timestamp.isoformat(),
                "agent_id": entry.agent_id,
                "action": entry.action,
                "workflow_run_id": str(entry.workflow_run_id) if entry.workflow_run_id else None,
                "task_id": str(entry.task_id) if entry.task_id else None,
                "llm_provider": entry.llm_provider,
                "llm_model": entry.llm_model,
                "tokens_used": entry.tokens_used,
                "duration_ms": entry.duration_ms,
                "success": entry.success,
                "error_message": entry.error_message,
                "input_summary": entry.input_summary[:200],
                "output_summary": entry.output_summary[:200],
            })

        return {"count": len(entries), "entries": entries}


# --- Internal aggregation helpers ---


async def _agent_performance(
    session: AsyncSession, agent_id: str | None, limit: int
) -> dict:
    """Aggregate agent performance: call count, avg duration, success rate, avg tokens."""
    stmt = select(
        AuditLogEntry.agent_id,
        func.count(AuditLogEntry.id).label("total_calls"),
        func.avg(AuditLogEntry.duration_ms).label("avg_duration_ms"),
        func.avg(AuditLogEntry.tokens_used).label("avg_tokens"),
        func.sum(AuditLogEntry.tokens_used).label("total_tokens"),
    ).group_by(AuditLogEntry.agent_id)

    if agent_id:
        stmt = stmt.where(AuditLogEntry.agent_id == agent_id)

    result = await session.execute(stmt)
    agents = {}
    for row in result:
        agents[row.agent_id] = {
            "total_calls": row.total_calls,
            "avg_duration_ms": round(row.avg_duration_ms or 0, 1),
            "avg_tokens": round(row.avg_tokens or 0, 0),
            "total_tokens": row.total_tokens or 0,
        }

    # Get error counts separately
    err_stmt = (
        select(
            AuditLogEntry.agent_id,
            func.count(AuditLogEntry.id).label("error_count"),
        )
        .where(AuditLogEntry.success.is_(False))
        .group_by(AuditLogEntry.agent_id)
    )
    if agent_id:
        err_stmt = err_stmt.where(AuditLogEntry.agent_id == agent_id)
    err_result = await session.execute(err_stmt)
    for row in err_result:
        if row.agent_id in agents:
            total = agents[row.agent_id]["total_calls"]
            agents[row.agent_id]["error_count"] = row.error_count
            agents[row.agent_id]["error_rate"] = round(row.error_count / total * 100, 1) if total else 0

    return {"metric_type": "agent_performance", "agents": agents}


async def _workflow_stats(
    session: AsyncSession, workflow_run_id: str | None, limit: int
) -> dict:
    """Workflow-level stats: agent calls per workflow, total duration, total tokens."""
    from aeco.models.workflow import WorkflowRun

    stmt = select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(limit)
    if workflow_run_id:
        import uuid
        stmt = select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(workflow_run_id))

    result = await session.execute(stmt)
    workflows = []
    for run in result.scalars():
        workflows.append({
            "id": str(run.id),
            "task_id": str(run.task_id),
            "status": run.status,
            "current_node": run.current_node,
            "state_snapshot": run.state_snapshot,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        })

    return {"metric_type": "workflow_stats", "workflows": workflows}


async def _cost_summary(
    session: AsyncSession, agent_id: str | None, limit: int
) -> dict:
    """Cost summary from spend records."""
    from aeco.models.budget import SpendRecord

    stmt = select(
        SpendRecord.agent_id,
        func.sum(SpendRecord.amount).label("total_cost"),
        func.sum(SpendRecord.tokens_used).label("total_tokens"),
        func.count(SpendRecord.id).label("call_count"),
    ).group_by(SpendRecord.agent_id)

    if agent_id:
        stmt = stmt.where(SpendRecord.agent_id == agent_id)

    result = await session.execute(stmt)
    costs = {}
    for row in result:
        costs[row.agent_id] = {
            "total_cost": round(row.total_cost or 0, 4),
            "total_tokens": row.total_tokens or 0,
            "call_count": row.call_count,
        }

    return {"metric_type": "cost_summary", "agents": costs}


async def _error_rates(
    session: AsyncSession, agent_id: str | None, limit: int
) -> dict:
    """Error rates with recent error messages."""
    stmt = (
        select(AuditLogEntry)
        .where(AuditLogEntry.success.is_(False))
        .order_by(AuditLogEntry.timestamp.desc())
        .limit(limit)
    )
    if agent_id:
        stmt = stmt.where(AuditLogEntry.agent_id == agent_id)

    result = await session.execute(stmt)
    errors = []
    for entry in result.scalars():
        errors.append({
            "agent_id": entry.agent_id,
            "action": entry.action,
            "error_message": entry.error_message,
            "timestamp": entry.timestamp.isoformat(),
            "workflow_run_id": str(entry.workflow_run_id) if entry.workflow_run_id else None,
        })

    return {"metric_type": "error_rates", "recent_errors": errors, "count": len(errors)}

"""API routes for scheduler and metric triggers."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

# These get set during app startup
_scheduler = None
_trigger_engine = None


def set_engines(scheduler, trigger_engine):
    global _scheduler, _trigger_engine
    _scheduler = scheduler
    _trigger_engine = trigger_engine


# --- Scheduled Jobs ---


class CreateJobRequest(BaseModel):
    name: str = Field(description="Job name")
    cron_expression: str = Field(description="5-field cron expression")
    callback_type: str = Field(default="portfolio_run", description="Callback type")
    callback_args: Dict[str, Any] = Field(default_factory=dict)


@router.get("/jobs")
async def list_jobs():
    if not _scheduler:
        return {"jobs": [], "error": "Scheduler not initialized"}
    return {"jobs": _scheduler.list_jobs()}


@router.post("/jobs")
async def create_job(req: CreateJobRequest):
    if not _scheduler:
        raise HTTPException(503, "Scheduler not initialized")

    # Resolve callback based on type
    callback = _resolve_callback(req.callback_type)
    if not callback:
        raise HTTPException(400, f"Unknown callback_type: {req.callback_type}")

    job = _scheduler.add_job(
        name=req.name,
        cron_expression=req.cron_expression,
        callback=callback,
        callback_args=req.callback_args,
    )
    return {"job": job.to_dict()}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    if not _scheduler:
        raise HTTPException(503, "Scheduler not initialized")
    if _scheduler.remove_job(job_id):
        return {"status": "removed"}
    raise HTTPException(404, "Job not found")


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    if not _scheduler:
        raise HTTPException(503, "Scheduler not initialized")
    if _scheduler.pause_job(job_id):
        return {"status": "paused"}
    raise HTTPException(404, "Job not found")


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    if not _scheduler:
        raise HTTPException(503, "Scheduler not initialized")
    if _scheduler.resume_job(job_id):
        return {"status": "resumed"}
    raise HTTPException(404, "Job not found")


# --- Metric Triggers ---


class CreateTriggerRequest(BaseModel):
    name: str
    metric_source: str = Field(description="stripe, facebook, telemetry, agent_metrics")
    metric_name: str
    comparison: str = Field(description="gt, lt, gte, lte")
    threshold: float
    cooldown_minutes: int = 60
    action_type: str = "portfolio_run"
    action_args: Dict[str, Any] = Field(default_factory=dict)


@router.get("/triggers")
async def list_triggers():
    if not _trigger_engine:
        return {"triggers": [], "error": "Trigger engine not initialized"}
    return {"triggers": _trigger_engine.list_triggers()}


@router.post("/triggers")
async def create_trigger(req: CreateTriggerRequest):
    if not _trigger_engine:
        raise HTTPException(503, "Trigger engine not initialized")

    from aeco.scheduler.triggers import MetricTrigger

    trigger = MetricTrigger(
        trigger_id=str(uuid.uuid4()),
        name=req.name,
        metric_source=req.metric_source,
        metric_name=req.metric_name,
        comparison=req.comparison,
        threshold=req.threshold,
        cooldown_minutes=req.cooldown_minutes,
        action_type=req.action_type,
        action_args=req.action_args,
    )
    _trigger_engine.add_trigger(trigger)
    return {"trigger": trigger.to_dict()}


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str):
    if not _trigger_engine:
        raise HTTPException(503, "Trigger engine not initialized")
    if _trigger_engine.remove_trigger(trigger_id):
        return {"status": "removed"}
    raise HTTPException(404, "Trigger not found")


@router.post("/triggers/check")
async def check_triggers():
    """Manually check all triggers now (for testing)."""
    if not _trigger_engine:
        raise HTTPException(503, "Trigger engine not initialized")
    fired = await _trigger_engine.check_all()
    return {"fired": fired, "count": len(fired)}


# --- Helpers ---


def _resolve_callback(callback_type: str):
    """Resolve a callback type string to an async function."""
    callbacks = {
        "portfolio_run": _portfolio_run_callback,
        "agent_review": _agent_review_callback,
    }
    return callbacks.get(callback_type)


async def _portfolio_run_callback(**kwargs):
    """Trigger a portfolio run via the API logic."""
    from aeco.api.routes_portfolio import _execute_portfolio
    # This is a simplified trigger — in production, would create a proper portfolio run
    return {"status": "triggered", "type": "portfolio_run", "args": kwargs}


async def _agent_review_callback(**kwargs):
    """Trigger an agent performance review."""
    return {"status": "triggered", "type": "agent_review", "args": kwargs}

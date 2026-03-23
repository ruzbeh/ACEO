"""Budget management API routes."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.budget.engine import BudgetEngine
from aeco.db.session import get_session, async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/budget", tags=["budget"])


def _get_engine() -> BudgetEngine:
    return BudgetEngine(async_session_factory)


# --- Request/Response models ---


class CreateBudgetRequest(BaseModel):
    name: str = Field(description="Budget name, e.g., 'March 2026 Sprint'")
    total_budget: float = Field(description="Total budget in USD")
    period_start: datetime = Field(description="Period start (ISO 8601)")
    period_end: datetime = Field(description="Period end (ISO 8601)")
    scope: str = Field(default="global", description="global, project, or agent")
    scope_id: Optional[str] = Field(default=None, description="Project name or agent_id")


class BudgetResponse(BaseModel):
    id: str
    name: str
    scope: str
    total_budget: float
    spent: float
    reserved: float
    remaining: float
    utilization_percent: float
    period_start: str
    period_end: str
    is_active: bool


class SpendRequest(BaseModel):
    agent_id: str
    amount: float
    category: str = "llm_tokens"
    description: str = ""
    workflow_run_id: Optional[str] = None
    task_id: Optional[str] = None
    tokens_used: Optional[int] = None
    llm_model: Optional[str] = None


# --- Endpoints ---


@router.post("/periods", response_model=BudgetResponse, status_code=201)
async def create_budget(req: CreateBudgetRequest):
    """Create a new budget period."""
    engine = _get_engine()
    budget = await engine.create_budget(
        name=req.name,
        total_budget=req.total_budget,
        period_start=req.period_start,
        period_end=req.period_end,
        scope=req.scope,
        scope_id=req.scope_id,
    )
    return BudgetResponse(
        id=str(budget.id),
        name=budget.name,
        scope=budget.scope,
        total_budget=budget.total_budget,
        spent=budget.spent,
        reserved=budget.reserved,
        remaining=budget.remaining,
        utilization_percent=budget.utilization_percent,
        period_start=budget.period_start.isoformat(),
        period_end=budget.period_end.isoformat(),
        is_active=budget.is_active,
    )


@router.get("/active")
async def get_active_budget(scope: str = "global", scope_id: Optional[str] = None):
    """Get the currently active budget for a scope."""
    engine = _get_engine()
    budget = await engine.get_active_budget(scope=scope, scope_id=scope_id)
    if not budget:
        raise HTTPException(status_code=404, detail="No active budget found")
    return await engine.get_budget_summary(budget.id)


@router.get("/periods/{budget_id}/summary")
async def get_budget_summary(budget_id: str):
    """Get full budget summary with spend breakdown."""
    engine = _get_engine()
    summary = await engine.get_budget_summary(uuid.UUID(budget_id))
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.post("/spend")
async def submit_spend(req: SpendRequest):
    """Submit a spend request for approval."""
    from aeco.budget.engine import SpendRequest as EngineSpendRequest
    from aeco.models.budget import SpendCategory

    engine = _get_engine()
    try:
        cat = SpendCategory(req.category)
    except ValueError:
        cat = SpendCategory.OTHER

    spend_req = EngineSpendRequest(
        agent_id=req.agent_id,
        amount=req.amount,
        category=cat,
        description=req.description,
        workflow_run_id=uuid.UUID(req.workflow_run_id) if req.workflow_run_id else None,
        task_id=uuid.UUID(req.task_id) if req.task_id else None,
        tokens_used=req.tokens_used,
        llm_model=req.llm_model,
    )
    decision = await engine.request_spend(spend_req)
    return decision.to_dict()


@router.get("/workflows/{workflow_run_id}/cost")
async def get_workflow_cost(workflow_run_id: str):
    """Get cost breakdown for a workflow run."""
    engine = _get_engine()
    return await engine.get_workflow_cost(uuid.UUID(workflow_run_id))


@router.get("/periods/{budget_id}/optimize")
async def get_optimization_report(budget_id: str):
    """Get optimization report with cost-saving suggestions."""
    engine = _get_engine()
    report = await engine.get_optimization_report(uuid.UUID(budget_id))
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report


@router.get("/periods/{budget_id}/spend-over-time")
async def get_spend_over_time(
    budget_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    group_by: str = "day",
):
    """Get spend aggregated over time (daily or weekly)."""
    engine = _get_engine()
    return await engine.get_spend_over_time(
        uuid.UUID(budget_id),
        from_date=from_date,
        to_date=to_date,
        group_by=group_by if group_by in ("day", "week") else "day",
    )


@router.get("/periods/{budget_id}/by-initiative")
async def get_spend_by_initiative_list(budget_id: str):
    """Get total spend per initiative for the budget period."""
    engine = _get_engine()
    return await engine.get_spend_by_initiative_list(uuid.UUID(budget_id))


@router.get("/periods/{budget_id}/recent-spend")
async def get_recent_spend(budget_id: str, limit: int = 50):
    """Get recent spend records with initiative, agent, and time."""
    engine = _get_engine()
    return await engine.get_recent_spend(uuid.UUID(budget_id), limit=limit)

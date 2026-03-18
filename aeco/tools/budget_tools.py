"""Budget tools for agents to read budget state and record spend."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from aeco.budget.engine import BudgetEngine
from aeco.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Lazily initialized engine (set up by main.py lifespan)
_engine: Optional[BudgetEngine] = None


def get_budget_engine() -> BudgetEngine:
    global _engine
    if _engine is None:
        _engine = BudgetEngine(async_session_factory)
    return _engine


def set_budget_engine(engine: BudgetEngine) -> None:
    global _engine
    _engine = engine


async def budget_read(
    scope: str = "global",
    scope_id: Optional[str] = None,
) -> dict:
    """Read the current budget status including spend breakdown, alerts, and optimization hints.

    Args:
        scope: Budget scope - "global", "project", or "agent".
        scope_id: Identifier for the scope (project name or agent_id). None for global.

    Returns:
        Budget summary with spend breakdown by category and agent, recent alerts,
        and current utilization.
    """
    engine = get_budget_engine()
    budget = await engine.get_active_budget(scope=scope, scope_id=scope_id)
    if not budget:
        return {
            "status": "no_budget",
            "message": f"No active budget found for scope={scope}, scope_id={scope_id}",
        }
    return await engine.get_budget_summary(budget.id)


async def budget_update(
    agent_id: str,
    amount: float,
    category: str = "llm_tokens",
    description: str = "",
    workflow_run_id: Optional[str] = None,
    task_id: Optional[str] = None,
    tokens_used: Optional[int] = None,
    llm_model: Optional[str] = None,
) -> dict:
    """Submit a spend request against the active budget.

    The budget engine will auto-approve, approve, deny, or escalate based on
    the amount and remaining budget. Returns the decision with any warnings
    and optimization hints.

    Args:
        agent_id: The agent requesting the spend.
        amount: Dollar amount to spend.
        category: One of "llm_tokens", "compute", "api_calls", "storage", "tooling", "other".
        description: What the spend is for.
        workflow_run_id: Associated workflow run (optional).
        task_id: Associated task (optional).
        tokens_used: Number of LLM tokens used (optional).
        llm_model: LLM model identifier (optional).

    Returns:
        Approval decision with status, reasoning, warnings, and optimization hints.
    """
    from aeco.models.budget import SpendCategory
    from aeco.budget.engine import SpendRequest

    engine = get_budget_engine()

    try:
        cat = SpendCategory(category)
    except ValueError:
        cat = SpendCategory.OTHER

    request = SpendRequest(
        agent_id=agent_id,
        amount=amount,
        category=cat,
        description=description,
        workflow_run_id=uuid.UUID(workflow_run_id) if workflow_run_id else None,
        task_id=uuid.UUID(task_id) if task_id else None,
        tokens_used=tokens_used,
        llm_model=llm_model,
    )
    decision = await engine.request_spend(request)
    return decision.to_dict()

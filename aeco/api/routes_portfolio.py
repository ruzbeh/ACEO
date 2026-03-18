"""Portfolio management API routes."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aeco.config import settings
from aeco.orchestrator.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Set by main.py after the portfolio graph is built
_compiled_portfolio_graph = None

# In-memory store for running portfolio states
_portfolio_runs: Dict[str, dict] = {}


def set_portfolio_graph(graph):
    global _compiled_portfolio_graph
    _compiled_portfolio_graph = graph


# --- Request/Response models ---


class RunPortfolioRequest(BaseModel):
    company_goals: List[str] = Field(description="High-level company goals")
    max_cycles: int = Field(default=2, ge=1, le=10, description="Max portfolio cycles")
    total_budget: float = Field(default=0.0, ge=0, description="Total budget for this portfolio run")
    workspace_path: Optional[str] = Field(default=None, description="Workspace path for initiative execution")


class PortfolioStatusResponse(BaseModel):
    portfolio_id: str
    current_phase: str
    cycle_count: int
    max_cycles: int
    budget_spent: float
    budget_remaining: float
    opportunities_found: int
    initiatives_funded: int
    initiatives_killed: int
    execution_results: int
    status: str  # running, completed, failed


# --- Endpoints ---


@router.post("/run", status_code=202)
async def run_portfolio(req: RunPortfolioRequest):
    """Start a portfolio cycle: discover opportunities, fund initiatives, evaluate outcomes."""
    if _compiled_portfolio_graph is None:
        raise HTTPException(status_code=503, detail="Portfolio graph not initialized")

    portfolio_id = str(uuid.uuid4())
    workspace_path = req.workspace_path or settings.workspace_path

    _portfolio_runs[portfolio_id] = {"status": "running", "state": None}

    asyncio.create_task(
        _execute_portfolio(portfolio_id, req.company_goals, req.max_cycles, req.total_budget, workspace_path)
    )

    return {
        "portfolio_id": portfolio_id,
        "status": "started",
        "message": f"Portfolio cycle started with {len(req.company_goals)} goals, max {req.max_cycles} cycles",
    }


@router.get("/{portfolio_id}/status", response_model=PortfolioStatusResponse)
async def get_portfolio_status(portfolio_id: str):
    """Get the current status of a portfolio run."""
    run = _portfolio_runs.get(portfolio_id)
    if not run:
        raise HTTPException(status_code=404, detail="Portfolio run not found")

    state = run.get("state") or {}
    return PortfolioStatusResponse(
        portfolio_id=portfolio_id,
        current_phase=state.get("current_phase", "starting"),
        cycle_count=state.get("cycle_count", 0),
        max_cycles=state.get("max_cycles", 0),
        budget_spent=state.get("budget_spent", 0),
        budget_remaining=state.get("budget_remaining", 0),
        opportunities_found=len(state.get("opportunities", [])),
        initiatives_funded=len(state.get("funded_initiatives", [])),
        initiatives_killed=len(state.get("killed_initiatives", [])),
        execution_results=len(state.get("execution_results", [])),
        status=run.get("status", "unknown"),
    )


@router.post("/{portfolio_id}/stop")
async def stop_portfolio(portfolio_id: str):
    """Request graceful stop of a portfolio run after the current cycle."""
    run = _portfolio_runs.get(portfolio_id)
    if not run:
        raise HTTPException(status_code=404, detail="Portfolio run not found")
    run["stop_requested"] = True
    return {"portfolio_id": portfolio_id, "message": "Stop requested; will complete after current cycle"}


@router.get("", response_model=list)
async def list_portfolio_runs():
    """List all portfolio runs."""
    return [
        {
            "portfolio_id": pid,
            "status": run.get("status", "unknown"),
            "current_phase": (run.get("state") or {}).get("current_phase", "unknown"),
        }
        for pid, run in _portfolio_runs.items()
    ]


# --- Internal ---


async def _execute_portfolio(
    portfolio_id: str,
    company_goals: list[str],
    max_cycles: int,
    total_budget: float,
    workspace_path: str,
) -> None:
    """Execute the portfolio workflow asynchronously."""
    try:
        initial_state: PortfolioState = {
            "portfolio_id": portfolio_id,
            "company_goals": company_goals,
            "opportunities": [],
            "active_initiatives": [],
            "portfolio_decisions": [],
            "funded_initiatives": [],
            "killed_initiatives": [],
            "execution_results": [],
            "total_budget": total_budget,
            "budget_spent": 0.0,
            "budget_remaining": total_budget,
            "current_phase": "opportunity_scan",
            "cycle_count": 0,
            "max_cycles": max_cycles,
            "workspace_path": workspace_path,
            "messages": [],
            "decisions": [],
            "errors": [],
        }

        logger.info(
            f"Starting portfolio run {portfolio_id}: "
            f"{len(company_goals)} goals, max {max_cycles} cycles, ${total_budget} budget"
        )

        final_state = await _compiled_portfolio_graph.ainvoke(initial_state)

        _portfolio_runs[portfolio_id] = {
            "status": "completed",
            "state": final_state,
        }

        cycles = final_state.get("cycle_count", 0)
        spent = final_state.get("budget_spent", 0)
        results = len(final_state.get("execution_results", []))
        logger.info(
            f"Portfolio {portfolio_id} completed: "
            f"{cycles} cycles, ${spent:.2f} spent, {results} initiative results"
        )

    except Exception as e:
        logger.error(f"Portfolio run failed: {e}", exc_info=True)
        _portfolio_runs[portfolio_id] = {
            "status": "failed",
            "state": {"current_phase": "failed", "error": str(e)},
        }

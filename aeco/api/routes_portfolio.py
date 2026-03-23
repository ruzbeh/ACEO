"""Portfolio management API routes.

Portfolio runs are persisted to the portfolio_cycles table.
In-memory dict _portfolio_runs holds live state for running portfolios.
On list/status, we merge in-memory (for running) with DB (for history).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aeco.config import settings
from aeco.events import event_bus
from aeco.orchestrator.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Set by main.py after the portfolio graph is built
_compiled_portfolio_graph = None

# In-memory store for RUNNING portfolio states (live progress updates)
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


class OpportunityItem(BaseModel):
    title: str = ""
    description: str = ""
    estimated_impact: str = ""

class DecisionItem(BaseModel):
    agent: str = ""
    phase: str = ""
    reasoning: str = ""
    funded: List[str] = []
    killed: List[str] = []
    scaled: List[str] = []

class ExecutionResultItem(BaseModel):
    title: str = ""
    initiative_id: str = ""
    action: str = ""
    verdict: str = ""
    budget_spent: float = 0
    tasks_executed: int = 0
    # Rich initiative internals
    prd: Optional[dict] = None
    design_document: Optional[str] = None
    security_review: Optional[dict] = None
    task_graph: List[dict] = []
    execution_details: List[dict] = []
    evaluation: Optional[dict] = None
    decisions: List[dict] = []
    north_star_metric: Optional[str] = None
    success_threshold: Optional[str] = None

class PortfolioStatusResponse(BaseModel):
    portfolio_id: str
    current_phase: str
    cycle_count: int
    max_cycles: int
    budget_spent: float
    budget_remaining: float
    total_budget: float = 0
    opportunities_found: int
    initiatives_funded: int
    initiatives_killed: int
    execution_results: int
    status: str  # running, completed, failed
    company_goals: List[str] = []
    opportunities: List[OpportunityItem] = []
    portfolio_decisions: List[DecisionItem] = []
    results: List[ExecutionResultItem] = []
    errors: List[str] = []
    messages: List[dict] = []
    # Structured company logs (agent/tool/state) streamed during this run — same schema as logs/company.log JSON lines
    live_log: List[dict] = []


# --- Helper: build status response from state dict ---

def _build_status_response(
    portfolio_id: str,
    state: dict,
    status: str,
    live_log: Optional[List[dict]] = None,
) -> PortfolioStatusResponse:
    """Build a PortfolioStatusResponse from a state dict."""
    raw_opps = state.get("opportunities", [])
    opportunities = []
    for o in raw_opps[-20:]:
        if isinstance(o, dict):
            opportunities.append(OpportunityItem(
                title=o.get("title", ""),
                description=o.get("description", ""),
                estimated_impact=o.get("estimated_impact", o.get("impact", "")),
            ))

    raw_decisions = state.get("portfolio_decisions", [])
    decisions = []
    for d in raw_decisions:
        if isinstance(d, dict):
            decisions.append(DecisionItem(
                agent=d.get("agent", ""),
                phase=d.get("phase", ""),
                reasoning=d.get("reasoning", d.get("decision", "")),
                funded=[f if isinstance(f, str) else f.get("title", "") for f in d.get("funded", [])],
                killed=d.get("killed", []),
                scaled=d.get("scaled", []),
            ))

    raw_results = state.get("execution_results", [])
    results = []
    for r in raw_results:
        if isinstance(r, dict):
            # Parse design_document if it's a JSON string
            design_doc = r.get("design_document")
            if isinstance(design_doc, str):
                try:
                    import json as _json
                    design_doc = _json.loads(design_doc)
                except Exception:
                    pass  # keep as string

            results.append(ExecutionResultItem(
                title=r.get("title", ""),
                initiative_id=r.get("initiative_id", ""),
                action=r.get("action", ""),
                verdict=r.get("verdict", ""),
                budget_spent=r.get("budget_spent", 0),
                tasks_executed=r.get("tasks_executed", 0),
                prd=r.get("prd"),
                design_document=str(design_doc) if design_doc else None,
                security_review=r.get("security_review"),
                task_graph=r.get("task_graph", []),
                execution_details=r.get("execution_details", []),
                evaluation=r.get("evaluation"),
                decisions=r.get("decisions", []),
                north_star_metric=r.get("north_star_metric"),
                success_threshold=str(r.get("success_threshold")) if r.get("success_threshold") else None,
            ))

    raw_messages = state.get("messages", [])
    messages = raw_messages[-50:] if raw_messages else []

    return PortfolioStatusResponse(
        portfolio_id=portfolio_id,
        current_phase=state.get("current_phase", "starting"),
        cycle_count=state.get("cycle_count", 0),
        max_cycles=state.get("max_cycles", 0),
        budget_spent=state.get("budget_spent", 0),
        budget_remaining=state.get("budget_remaining", 0),
        total_budget=state.get("total_budget", 0),
        opportunities_found=len(state.get("opportunities", [])),
        initiatives_funded=len(state.get("funded_initiatives", [])),
        initiatives_killed=len(state.get("killed_initiatives", [])),
        execution_results=len(state.get("execution_results", [])),
        status=status,
        company_goals=state.get("company_goals", []),
        opportunities=opportunities,
        portfolio_decisions=decisions,
        results=results,
        errors=state.get("errors", []),
        messages=messages,
        live_log=live_log or [],
    )


_LIVE_LOG_MAX = 2000


def append_portfolio_live_log(portfolio_id: str, record: dict[str, Any]) -> None:
    """Append one company JSON log line to the in-memory run and notify WebSocket clients."""
    run = _portfolio_runs.get(portfolio_id)
    if not run:
        return
    dq = run.setdefault("live_log", deque(maxlen=_LIVE_LOG_MAX))
    dq.append(record)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            event_bus.emit(
                "portfolio.live_log",
                {"portfolio_id": portfolio_id, "line": record},
            )
        )
    except RuntimeError:
        pass


# --- Endpoints ---


@router.post("/run", status_code=202)
async def run_portfolio(req: RunPortfolioRequest):
    """Start a portfolio cycle: discover opportunities, fund initiatives, evaluate outcomes."""
    if _compiled_portfolio_graph is None:
        raise HTTPException(status_code=503, detail="Portfolio graph not initialized")

    portfolio_id = str(uuid.uuid4())
    workspace_path = req.workspace_path or settings.workspace_path
    now = datetime.now(timezone.utc)

    # Create DB record
    try:
        from aeco.db.session import async_session_factory
        from aeco.models.portfolio_cycle import PortfolioCycle
        async with async_session_factory() as session:
            cycle = PortfolioCycle(
                id=uuid.UUID(portfolio_id),
                status="running",
                current_phase="starting",
                company_goals=req.company_goals,
                max_cycles=req.max_cycles,
                workspace_path=workspace_path,
                total_budget=req.total_budget,
                budget_remaining=req.total_budget,
                started_at=now,
                updated_at=now,
            )
            session.add(cycle)
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to persist portfolio run to DB: {e}")

    # In-memory for live progress
    _portfolio_runs[portfolio_id] = {
        "status": "running",
        "state": None,
        "started_at": now.isoformat(),
        "completed_at": None,
        "live_log": deque(maxlen=_LIVE_LOG_MAX),
    }

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
    """Get the current status of a portfolio run (live from memory or historical from DB)."""
    # First check in-memory (running or recently completed)
    run = _portfolio_runs.get(portfolio_id)
    if run:
        state = run.get("state") or {}
        ll = run.get("live_log")
        live_log = list(ll) if ll else []
        return _build_status_response(portfolio_id, state, run.get("status", "unknown"), live_log=live_log)

    # Fall back to DB
    try:
        from aeco.db.session import async_session_factory
        from aeco.models.portfolio_cycle import PortfolioCycle
        async with async_session_factory() as session:
            db_cycle = await session.get(PortfolioCycle, uuid.UUID(portfolio_id))
            if db_cycle:
                return PortfolioStatusResponse(**db_cycle.to_status_dict())
    except Exception as e:
        logger.warning(f"DB lookup failed for portfolio {portfolio_id}: {e}")

    raise HTTPException(status_code=404, detail="Portfolio run not found")


@router.post("/{portfolio_id}/stop")
async def stop_portfolio(portfolio_id: str):
    """Request graceful stop of a portfolio run after the current cycle."""
    run = _portfolio_runs.get(portfolio_id)
    if not run:
        raise HTTPException(status_code=404, detail="Portfolio run not found or not running")
    run["stop_requested"] = True
    return {"portfolio_id": portfolio_id, "message": "Stop requested; will complete after current cycle"}


@router.get("", response_model=list)
async def list_portfolio_runs():
    """List all portfolio runs (newest first). Merges in-memory running + DB history."""
    seen_ids = set()
    items = []

    # In-memory running/recent
    for pid, run in _portfolio_runs.items():
        seen_ids.add(pid)
        items.append({
            "portfolio_id": pid,
            "status": run.get("status", "unknown"),
            "current_phase": (run.get("state") or {}).get("current_phase", "starting"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "cycle_count": (run.get("state") or {}).get("cycle_count", 0),
            "max_cycles": (run.get("state") or {}).get("max_cycles", 0),
        })

    # DB history (last 50, excluding already-seen)
    try:
        from aeco.db.session import async_session_factory
        from aeco.models.portfolio_cycle import PortfolioCycle
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(PortfolioCycle)
                .order_by(PortfolioCycle.started_at.desc())
                .limit(50)
            )
            for db_cycle in result.scalars():
                pid = str(db_cycle.id)
                if pid not in seen_ids:
                    items.append(db_cycle.to_list_item())
    except Exception as e:
        logger.warning(f"Failed to load portfolio history from DB: {e}")

    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return items


# --- Approval Queue ---


@router.get("/approvals")
async def list_approvals():
    """Get all pending approval requests."""
    from aeco.db.session import async_session_factory
    from aeco.models.approval import ApprovalRequest as ApprovalModel, ApprovalStatus
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(ApprovalModel).order_by(ApprovalModel.created_at.desc())
        )
        approvals = result.scalars().all()
        return [
            {
                "id": a.id,
                "portfolio_id": a.portfolio_id,
                "initiative_title": a.initiative_title,
                "action": a.action,
                "reasoning": a.reasoning,
                "allocated_budget": a.allocated_budget,
                "blast_radius": a.blast_radius,
                "requested_by": a.requested_by,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in approvals
        ]


@router.post("/approvals/{approval_id}/approve")
async def approve_request(approval_id: str):
    """Approve a pending approval request."""
    from datetime import datetime as dt, timezone as tz
    from aeco.db.session import async_session_factory
    from aeco.models.approval import ApprovalRequest as ApprovalModel, ApprovalStatus

    async with async_session_factory() as session:
        approval = await session.get(ApprovalModel, approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != ApprovalStatus.PENDING.value:
            raise HTTPException(status_code=400, detail=f"Already {approval.status}")
        approval.status = ApprovalStatus.APPROVED.value
        approval.reviewed_at = dt.now(tz.utc)
        await session.commit()
        return {"id": approval_id, "status": "approved"}


@router.post("/approvals/{approval_id}/reject")
async def reject_request(approval_id: str):
    """Reject a pending approval request."""
    from datetime import datetime as dt, timezone as tz
    from aeco.db.session import async_session_factory
    from aeco.models.approval import ApprovalRequest as ApprovalModel, ApprovalStatus

    async with async_session_factory() as session:
        approval = await session.get(ApprovalModel, approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != ApprovalStatus.PENDING.value:
            raise HTTPException(status_code=400, detail=f"Already {approval.status}")
        approval.status = ApprovalStatus.REJECTED.value
        approval.reviewed_at = dt.now(tz.utc)
        await session.commit()
        return {"id": approval_id, "status": "rejected"}


# --- Internal ---


async def _persist_state(portfolio_id: str, state: dict, status: str = "running") -> None:
    """Persist current portfolio state to DB (best-effort, non-blocking)."""
    try:
        from aeco.db.session import async_session_factory
        from aeco.models.portfolio_cycle import PortfolioCycle
        async with async_session_factory() as session:
            db_cycle = await session.get(PortfolioCycle, uuid.UUID(portfolio_id))
            if db_cycle:
                db_cycle.status = status
                db_cycle.update_from_state(state)
                if status in ("completed", "failed", "stopped"):
                    db_cycle.completed_at = datetime.now(timezone.utc)
                await session.commit()
    except Exception as e:
        logger.debug(f"Failed to persist portfolio state: {e}")


async def _execute_portfolio(
    portfolio_id: str,
    company_goals: list[str],
    max_cycles: int,
    total_budget: float,
    workspace_path: str,
) -> None:
    """Execute the portfolio workflow asynchronously."""
    from aeco.logging.company_logger import portfolio_run_id

    ctx_token = portfolio_run_id.set(portfolio_id)
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

        run_entry = _portfolio_runs.get(portfolio_id) or {}
        run_entry["state"] = dict(initial_state)
        _portfolio_runs[portfolio_id] = run_entry

        final_state = None
        try:
            async for chunk in _compiled_portfolio_graph.astream(
                initial_state, stream_mode="values"
            ):
                for _node_name, state in chunk.items():
                    if isinstance(state, dict):
                        final_state = state
                        _portfolio_runs[portfolio_id]["state"] = state
                        # Persist progress to DB periodically
                        await _persist_state(portfolio_id, state, "running")
        except Exception as stream_err:
            logger.warning(f"Portfolio stream failed, falling back to ainvoke: {stream_err}")
            final_state = await _compiled_portfolio_graph.ainvoke(initial_state)
            _portfolio_runs[portfolio_id]["state"] = final_state

        if final_state is None:
            final_state = dict(initial_state)

        now_iso = datetime.now(timezone.utc).isoformat()
        _portfolio_runs[portfolio_id]["status"] = "completed"
        _portfolio_runs[portfolio_id]["completed_at"] = now_iso

        # Persist final state to DB
        await _persist_state(portfolio_id, final_state, "completed")

        cycles = final_state.get("cycle_count", 0)
        spent = final_state.get("budget_spent", 0)
        results = len(final_state.get("execution_results", []))
        logger.info(
            f"Portfolio {portfolio_id} completed: "
            f"{cycles} cycles, ${spent:.2f} spent, {results} initiative results"
        )

    except Exception as e:
        logger.error(f"Portfolio run failed: {e}", exc_info=True)
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = _portfolio_runs.get(portfolio_id) or {}
        failed_state = {**(existing.get("state") or {}), "current_phase": "failed", "error": str(e)}
        _portfolio_runs[portfolio_id] = {
            **existing,
            "status": "failed",
            "state": failed_state,
            "completed_at": now_iso,
        }
        # Persist failure to DB
        await _persist_state(portfolio_id, failed_state, "failed")
    finally:
        portfolio_run_id.reset(ctx_token)


from aeco.logging.portfolio_live_buffer import register_portfolio_live_append

register_portfolio_live_append(append_portfolio_live_log)

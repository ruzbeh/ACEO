"""Initiative management API routes."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.config import settings
from aeco.db.session import async_session_factory, get_session
from aeco.events import event_bus
from aeco.models.initiative import Initiative, InitiativeStatus, InitiativeVerdict
from aeco.orchestrator.initiative_state import InitiativeState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/initiatives", tags=["initiatives"])

# In-memory live log for initiative runs (company JSON lines + node steps)
_initiative_runs: dict[str, dict[str, Any]] = {}
_LIVE_LOG_MAX = 2000


def append_initiative_live_log(initiative_id: str, record: dict[str, Any]) -> None:
    """Append one log line to the active initiative run and notify WebSocket clients."""
    run = _initiative_runs.get(initiative_id)
    if not run:
        return
    dq = run.setdefault("live_log", deque(maxlen=_LIVE_LOG_MAX))
    dq.append(record)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            event_bus.emit(
                "initiative.live_log",
                {"initiative_id": initiative_id, "line": record},
            )
        )
    except RuntimeError:
        pass

# Set by main.py after the initiative graph is built
_compiled_initiative_graph = None


def set_initiative_graph(graph):
    global _compiled_initiative_graph
    _compiled_initiative_graph = graph


# --- Request/Response models ---


class CreateInitiativeRequest(BaseModel):
    title: str = Field(description="Initiative title")
    goal: str = Field(description="What this initiative aims to achieve")
    hypothesis: str = Field(default="", description="Hypothesis to validate")
    workspace_path: Optional[str] = Field(default=None, description="Workspace path for code execution")


class InitiativeResponse(BaseModel):
    id: str
    title: str
    goal: str
    hypothesis: str
    status: str
    verdict: str
    north_star_metric: Optional[str]
    created_at: str
    run_started_at: Optional[str] = None  # ISO — exact time the workflow was last started (Run)

    model_config = {"from_attributes": True}


class RunInitiativeRequest(BaseModel):
    initiative_id: str
    workspace_path: Optional[str] = None


def _resolve_workspace_path(path: str) -> str:
    """Resolve to absolute path and ensure it exists and is a directory."""
    if not path or not path.strip():
        path = settings.workspace_path
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Workspace path does not exist: {resolved}. "
                "Create the directory or use an absolute path to an existing project (e.g. /path/to/your/project)."
            ),
        )
    if not resolved.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path is not a directory: {resolved}.",
        )
    return str(resolved)


# --- Endpoints ---


@router.post("", response_model=InitiativeResponse, status_code=201)
async def create_initiative(
    req: CreateInitiativeRequest, session: AsyncSession = Depends(get_session)
):
    """Create a new initiative."""
    initiative = Initiative(
        title=req.title,
        goal=req.goal,
        hypothesis=req.hypothesis,
    )
    session.add(initiative)
    await session.commit()
    await session.refresh(initiative)
    return _to_response(initiative)


@router.get("", response_model=list[InitiativeResponse])
async def list_initiatives(session: AsyncSession = Depends(get_session)):
    """List all initiatives."""
    result = await session.execute(
        select(Initiative).order_by(Initiative.created_at.desc())
    )
    return [_to_response(i) for i in result.scalars()]


@router.get("/{initiative_id}", response_model=InitiativeResponse)
async def get_initiative(
    initiative_id: str, session: AsyncSession = Depends(get_session)
):
    """Get initiative details."""
    initiative = await session.get(Initiative, uuid.UUID(initiative_id))
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")
    return _to_response(initiative)


@router.post("/run", status_code=202)
async def run_initiative(req: RunInitiativeRequest):
    """Trigger the initiative workflow (PM → Architect → TaskPlanner → Execute → Evaluate)."""
    if _compiled_initiative_graph is None:
        raise HTTPException(status_code=503, detail="Initiative graph not initialized")

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        initiative = await session.get(Initiative, uuid.UUID(req.initiative_id))
        if not initiative:
            raise HTTPException(status_code=404, detail="Initiative not found")

        initiative.status = InitiativeStatus.PLANNING.value
        initiative.run_started_at = now
        await session.commit()

    try:
        ws_path = _resolve_workspace_path(req.workspace_path or settings.workspace_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid workspace path: {e}") from e

    iid = str(initiative.id)
    _initiative_runs[iid] = {
        "started_at": now.isoformat(),
        "live_log": deque(maxlen=_LIVE_LOG_MAX),
    }

    asyncio.create_task(
        _execute_initiative(initiative, ws_path)
    )

    return {
        "initiative_id": str(initiative.id),
        "status": "started",
        "message": "Initiative workflow triggered",
    }


@router.post("/{initiative_id}/kill", response_model=InitiativeResponse)
async def kill_initiative(
    initiative_id: str, session: AsyncSession = Depends(get_session)
):
    """Mark initiative as killed (closed with verdict kill). Preserved even if workflow completes later."""
    initiative = await session.get(Initiative, uuid.UUID(initiative_id))
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiative not found")
    initiative.status = InitiativeStatus.CLOSED.value
    initiative.verdict = InitiativeVerdict.KILL.value
    await session.commit()
    await session.refresh(initiative)
    return _to_response(initiative)


@router.get("/{initiative_id}/decisions")
async def get_initiative_decisions(initiative_id: str):
    """Get all decisions made during an initiative."""
    from aeco.memory.decision_ledger import DecisionLedgerStore
    ledger = DecisionLedgerStore(async_session_factory)
    decisions = await ledger.get_by_initiative(uuid.UUID(initiative_id))
    return {"initiative_id": initiative_id, "decisions": decisions}


@router.get("/{initiative_id}/live-log")
async def get_initiative_live_log(
    initiative_id: str, session: AsyncSession = Depends(get_session)
):
    """Return buffered log lines and exact workflow start time (memory + DB fallback)."""
    run = _initiative_runs.get(initiative_id)
    lines = list(run["live_log"]) if run and run.get("live_log") else []
    started = (run or {}).get("started_at")
    if not started:
        init = await session.get(Initiative, uuid.UUID(initiative_id))
        if init and init.run_started_at:
            started = init.run_started_at.isoformat()
    return {
        "initiative_id": initiative_id,
        "run_started_at": started,
        "lines": lines,
    }


@router.get("/{initiative_id}/spend")
async def get_initiative_spend(initiative_id: str, budget_id: Optional[str] = None):
    """Get budget spend breakdown for this initiative (optionally scoped to a budget period)."""
    from aeco.budget.engine import BudgetEngine
    engine = BudgetEngine(async_session_factory)
    bid = uuid.UUID(budget_id) if budget_id else None
    return await engine.get_spend_by_initiative(uuid.UUID(initiative_id), budget_id=bid)


# --- Internal ---


async def _execute_initiative(initiative: Initiative, workspace_path: str) -> None:
    """Execute the initiative workflow asynchronously."""
    from aeco.logging.company_logger import initiative_run_id

    token = initiative_run_id.set(str(initiative.id))
    try:
        initial_state: InitiativeState = {
            "initiative_id": str(initiative.id),
            "title": initiative.title,
            "goal": initiative.goal,
            "hypothesis": initiative.hypothesis,
            "workspace_path": workspace_path,
            "project_context": None,
            "prd": None,
            "design_document": None,
            "security_review": None,
            "task_graph": [],
            "execution_results": [],
            "evaluation": None,
            "north_star_metric": None,
            "local_metrics": [],
            "success_threshold": None,
            "evaluation_window_days": 7,
            "decisions": [],
            "current_phase": "intake",
            "verdict": None,
            "iteration_count": 0,
            "max_iterations": 3,
            "messages": [],
            "errors": [],
            "budget_spent": 0.0,
            "budget_remaining": 0.0,
        }

        logger.info(f"Starting initiative workflow for '{initiative.title}'")
        final_state = await _compiled_initiative_graph.ainvoke(initial_state)

        verdict = final_state.get("verdict", "kill")
        iterations = final_state.get("iteration_count", 0)
        tasks_executed = len(final_state.get("execution_results", []))

        logger.info(
            f"Initiative '{initiative.title}' completed: "
            f"verdict={verdict}, iterations={iterations}, tasks={tasks_executed}"
        )

        # Update initiative in DB (skip if already closed e.g. user clicked Kill)
        async with async_session_factory() as session:
            db_init = await session.get(Initiative, initiative.id)
            if db_init and db_init.status != InitiativeStatus.CLOSED.value:
                db_init.status = InitiativeStatus.CLOSED.value
                db_init.verdict = verdict
                db_init.north_star_metric = final_state.get("north_star_metric")
                db_init.task_graph_snapshot = final_state.get("task_graph", [])
                await session.commit()

    except Exception as e:
        logger.error(f"Initiative workflow failed: {e}", exc_info=True)
        async with async_session_factory() as session:
            db_init = await session.get(Initiative, initiative.id)
            if db_init:
                db_init.status = InitiativeStatus.CLOSED.value
                db_init.verdict = InitiativeVerdict.KILL.value
                await session.commit()
    finally:
        initiative_run_id.reset(token)


from aeco.logging.initiative_live_buffer import register_initiative_live_append

register_initiative_live_append(append_initiative_live_log)


def _to_response(i: Initiative) -> InitiativeResponse:
    return InitiativeResponse(
        id=str(i.id),
        title=i.title,
        goal=i.goal,
        hypothesis=i.hypothesis,
        status=i.status,
        verdict=i.verdict,
        north_star_metric=i.north_star_metric,
        created_at=i.created_at.isoformat(),
        run_started_at=i.run_started_at.isoformat() if i.run_started_at else None,
    )

"""Fast-track API route: quick 3-step pipeline for small tasks.

POST /api/fast-track — submit a plain-text request, get code shipped in <5 minutes.
GET /api/fast-track/{request_id} — check status of a running fast-track.
GET /api/fast-track — list recent fast-track runs.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aeco.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fast-track", tags=["fast-track"])

# Set by main.py after the fast-track graph is built
_compiled_fast_track_graph = None

# In-memory store for running/completed fast-track runs
_fast_track_runs: Dict[str, dict] = {}


def set_fast_track_graph(graph):
    global _compiled_fast_track_graph
    _compiled_fast_track_graph = graph


# --- Request/Response models ---


class FastTrackRequest(BaseModel):
    request: str = Field(description="Plain-text description of what to build/change")
    workspace_path: Optional[str] = Field(default=None, description="Workspace path (uses default if None)")
    budget_limit: float = Field(default=20.0, ge=0, le=100, description="Max budget for this fast-track run")
    # M3: scaffold hints
    project_name: Optional[str] = Field(default=None, description="Project name for scaffolding (e.g. 'headshot-ai')")
    stack: Optional[str] = Field(default=None, description="Tech stack template (e.g. 'nextjs-supabase-stripe')")
    features: Optional[List[str]] = Field(default=None, description="Feature add-ons: auth, payments, file-upload, ai-generation")


class FastTrackStatusResponse(BaseModel):
    request_id: str
    request: str
    status: str  # running, done, escalated, error
    current_phase: str
    plan: Optional[dict] = None
    files_changed: List[str] = []
    preview_url: Optional[str] = None
    git_commit: Optional[str] = None
    scaffold_result: Optional[dict] = None
    smoke_result: Optional[dict] = None
    escalate_to_initiative: bool = False
    escalate_reason: Optional[str] = None
    errors: List[str] = []
    messages: List[dict] = []
    decisions: List[dict] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class FastTrackListItem(BaseModel):
    request_id: str
    request: str
    status: str
    preview_url: Optional[str] = None
    started_at: Optional[str] = None


# --- Endpoints ---


@router.post("", status_code=202)
async def run_fast_track(body: FastTrackRequest):
    """Submit a fast-track request. Returns immediately with a request_id."""
    if _compiled_fast_track_graph is None:
        raise HTTPException(status_code=503, detail="Fast-track graph not initialized")

    request_id = str(uuid.uuid4())
    workspace = body.workspace_path or settings.workspace_path

    initial_state = {
        "request_id": request_id,
        "request": body.request,
        "workspace_path": workspace,
        "project_context": None,
        # Scaffold (M3)
        "scaffold_result": None,
        "is_new_project": bool(body.stack or body.features),
        "stack": body.stack,
        "features": body.features or [],
        "project_name": body.project_name,
        # Architect
        "plan": None,
        "escalate_to_initiative": False,
        # Build
        "build_result": None,
        "files_changed": [],
        # Ship
        "git_result": None,
        "deploy_result": None,
        "preview_url": None,
        # Verify (M3)
        "smoke_result": None,
        # Control
        "current_phase": "intake",
        "budget_spent": 0.0,
        "budget_remaining": body.budget_limit,
        "decisions": [],
        "messages": [],
        "errors": [],
    }

    _fast_track_runs[request_id] = {
        "state": initial_state,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    # Run graph asynchronously
    asyncio.create_task(_execute_fast_track(request_id, initial_state))

    return {
        "request_id": request_id,
        "status": "running",
        "message": f"Fast-track started for: {body.request[:100]}",
    }


async def _execute_fast_track(request_id: str, initial_state: dict):
    """Execute the fast-track graph and update in-memory state."""
    try:
        result = await _compiled_fast_track_graph.ainvoke(initial_state)

        run = _fast_track_runs.get(request_id, {})
        run["state"] = result

        if result.get("escalate_to_initiative"):
            run["status"] = "escalated"
        elif result.get("errors"):
            run["status"] = "error" if not result.get("preview_url") else "done"
        else:
            run["status"] = "done"

        run["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error(f"Fast-track {request_id} failed: {e}", exc_info=True)
        run = _fast_track_runs.get(request_id, {})
        run["status"] = "error"
        run["completed_at"] = datetime.now(timezone.utc).isoformat()
        if "state" in run:
            run["state"]["errors"] = run["state"].get("errors", []) + [str(e)]


@router.get("/{request_id}")
async def get_fast_track_status(request_id: str) -> FastTrackStatusResponse:
    """Get status of a fast-track run."""
    run = _fast_track_runs.get(request_id)
    if not run:
        raise HTTPException(status_code=404, detail="Fast-track run not found")

    state = run["state"]
    git_result = state.get("git_result") or {}

    return FastTrackStatusResponse(
        request_id=request_id,
        request=state.get("request", ""),
        status=run["status"],
        current_phase=state.get("current_phase", "unknown"),
        plan=state.get("plan"),
        files_changed=state.get("files_changed", []),
        preview_url=state.get("preview_url"),
        git_commit=git_result.get("commit"),
        escalate_to_initiative=state.get("escalate_to_initiative", False),
        escalate_reason=state.get("plan", {}).get("escalate_reason") if state.get("escalate_to_initiative") else None,
        errors=state.get("errors", []),
        messages=state.get("messages", []),
        decisions=state.get("decisions", []),
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
    )


@router.get("")
async def list_fast_track_runs() -> List[FastTrackListItem]:
    """List recent fast-track runs (newest first, max 50)."""
    items = []
    for rid, run in sorted(
        _fast_track_runs.items(),
        key=lambda x: x[1].get("started_at", ""),
        reverse=True,
    )[:50]:
        state = run["state"]
        items.append(FastTrackListItem(
            request_id=rid,
            request=state.get("request", "")[:200],
            status=run["status"],
            preview_url=state.get("preview_url"),
            started_at=run.get("started_at"),
        ))
    return items

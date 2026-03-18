"""Workflow execution API routes."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.config import settings
from aeco.db.session import async_session_factory, get_session
from aeco.logging.company_logger import (
    log_workflow_completed,
    log_workflow_failed,
    log_workflow_start,
)
from aeco.models.task import Task, TaskStatus
from aeco.models.workflow import WorkflowRun
from aeco.orchestrator.state import AECOState
from aeco.projects.scanner import scan_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# Will be set by main.py after graph is built
_compiled_graph = None


def set_graph(graph):
    global _compiled_graph
    _compiled_graph = graph


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
                "Create the directory or use an absolute path to an existing project."
            ),
        )
    if not resolved.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path is not a directory: {resolved}.",
        )
    return str(resolved)


async def trigger_workflow_for_task(
    task_id: uuid.UUID,
    workspace_path: Optional[str] = None,
) -> Optional[WorkflowRun]:
    """Create a workflow run for the given task and execute it in the background.
    Returns the WorkflowRun if started, or None if graph not ready or task not found.
    """
    if _compiled_graph is None:
        logger.warning("Workflow graph not initialized; cannot trigger workflow")
        return None
    ws_path = workspace_path or settings.workspace_path
    project_context = None
    try:
        ctx = await scan_project(ws_path)
        project_context = ctx.model_dump()
    except Exception as e:
        logger.warning(f"Failed to scan project at {ws_path}: {e}")
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            logger.warning(f"Task {task_id} not found; cannot trigger workflow")
            return None
        run = WorkflowRun(task_id=task.id)
        session.add(run)
        task.status = TaskStatus.IN_PROGRESS
        task.workflow_run_id = run.id
        await session.commit()
        await session.refresh(run)
    asyncio.create_task(
        _execute_workflow(run.id, task, ws_path, project_context)
    )
    logger.info(f"Triggered workflow run {run.id} for task {task_id}")
    return run


class RunWorkflowRequest(BaseModel):
    task_id: str
    workspace_path: Optional[str] = None
    project_name: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    task_id: str
    status: str
    current_node: str
    started_at: str
    completed_at: Optional[str]
    error: Optional[str] = None  # when status is "failed", message from state_snapshot

    model_config = {"from_attributes": True}


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    limit: int = 50, session: AsyncSession = Depends(get_session)
):
    """List recent workflow runs, newest first."""
    result = await session.execute(
        select(WorkflowRun).order_by(WorkflowRun.started_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return [_to_response(r) for r in runs]


@router.post("/run", response_model=WorkflowResponse, status_code=201)
async def run_workflow(
    req: RunWorkflowRequest, session: AsyncSession = Depends(get_session)
):
    """Trigger a workflow run for a task."""
    if _compiled_graph is None:
        raise HTTPException(status_code=503, detail="Workflow graph not initialized")

    task = await session.get(Task, uuid.UUID(req.task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Resolve and validate workspace path
    try:
        ws_path = _resolve_workspace_path(req.workspace_path or settings.workspace_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid workspace path: {e}") from e

    # Scan the project for context
    project_context: Optional[dict] = None
    try:
        ctx = await scan_project(ws_path)
        project_context = ctx.model_dump()
    except Exception as e:
        logger.warning(f"Failed to scan project at {ws_path}: {e}")

    # Create workflow run record
    run = WorkflowRun(task_id=task.id)
    session.add(run)
    task.status = TaskStatus.IN_PROGRESS
    task.workflow_run_id = run.id
    await session.commit()
    await session.refresh(run)

    # Launch workflow in background
    asyncio.create_task(_execute_workflow(run.id, task, ws_path, project_context))

    return _to_response(run)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str, session: AsyncSession = Depends(get_session)
):
    """Get workflow run status."""
    run = await session.get(WorkflowRun, uuid.UUID(workflow_id))
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_response(run)


async def _execute_workflow(
    run_id: uuid.UUID,
    task: Task,
    workspace_path: str,
    project_context: Optional[dict],
) -> None:
    """Execute the LangGraph workflow asynchronously."""
    try:
        initial_state: AECOState = {
            "workflow_run_id": str(run_id),
            "task_id": str(task.id),
            "clickup_task_id": task.clickup_task_id,
            "task_title": task.title,
            "task_description": task.description,
            "status": "todo",
            "workspace_path": workspace_path,
            "project_context": project_context,
            "messages": [],
            "design_document": None,
            "code_artifacts": [],
            "test_results": None,
            "review_feedback": None,
            "current_agent": None,
            "next_action": None,
            "iteration_count": 0,
            "max_iterations": 5,
            "budget_spent": 0.0,
            "budget_remaining": 0.0,
            "budget_warnings": [],
            "budget_optimization_hints": [],
            "budget_approved": True,
            "errors": [],
        }

        log_workflow_start(
            run_id=str(run_id),
            task_id=str(task.id),
            task_title=task.title,
            workspace_path=workspace_path,
        )
        logger.info(f"Starting workflow {run_id} for task '{task.title}' in workspace {workspace_path}")

        # Persist "starting" immediately so UI shows the run has begun
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.current_node = "starting"
                run.state_snapshot = {"status": "todo", "message": "Workflow started"}
                await session.commit()

        # Map workflow state status to TaskStatus so the task pipeline reflects current phase
        _STATE_TO_TASK_STATUS = {
            "intake": TaskStatus.IN_PROGRESS,
            "architect_design": TaskStatus.ARCHITECT_DESIGN,
            "engineering": TaskStatus.ENGINEERING,
            "qa_review": TaskStatus.QA_REVIEW,
            "done": TaskStatus.DONE,
        }

        async def persist_progress(node_name: str, state: dict) -> None:
            async with async_session_factory() as session:
                run = await session.get(WorkflowRun, run_id)
                if run:
                    run.current_node = node_name
                    run.state_snapshot = {
                        "status": state.get("status"),
                        "iterations": state.get("iteration_count", 0),
                        "current_agent": state.get("current_agent"),
                        "files_created": len(state.get("code_artifacts", [])),
                        "budget_spent": state.get("budget_spent", 0.0),
                        "budget_remaining": state.get("budget_remaining", 0.0),
                    }
                # Update task status so Task Lifecycle pipeline shows current phase
                workflow_status = state.get("status")
                if workflow_status:
                    task_status = _STATE_TO_TASK_STATUS.get(
                        workflow_status, TaskStatus.IN_PROGRESS
                    )
                    db_task = await session.get(Task, task.id)
                    if db_task:
                        db_task.status = task_status
                await session.commit()

        final_state = None
        try:
            async for chunk in _compiled_graph.astream(
                initial_state, stream_mode="values"
            ):
                for node_name, state in chunk.items():
                    if isinstance(state, dict):
                        final_state = state
                        await persist_progress(node_name, state)
        except Exception as stream_err:
            logger.warning(f"Workflow stream failed, falling back to ainvoke: {stream_err}")
            final_state = None
        if final_state is None:
            final_state = await _compiled_graph.ainvoke(initial_state)

        status = final_state.get("status", "unknown")
        iterations = final_state.get("iteration_count", 0)
        files_created = len(final_state.get("code_artifacts", []))

        log_workflow_completed(
            run_id=str(run_id),
            task_id=str(task.id),
            status=status,
            iterations=iterations,
            files_created=files_created,
        )
        logger.info(f"Workflow {run_id} completed with status: {status}")

        # Update workflow run and task
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.status = "completed"
                run.current_node = "done"
                run.state_snapshot = {
                    "status": status,
                    "iterations": iterations,
                    "files_created": files_created,
                }

            db_task = await session.get(Task, task.id)
            if db_task:
                db_task.status = TaskStatus.DONE
                db_task.clickup_task_id = final_state.get("clickup_task_id")

            await session.commit()

    except Exception as e:
        log_workflow_failed(run_id=str(run_id), task_id=str(task.id), error=str(e))
        logger.error(f"Workflow {run_id} failed: {e}", exc_info=True)
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.status = "failed"
                run.current_node = "failed"
                run.state_snapshot = {"error": str(e)}
            db_task = await session.get(Task, task.id)
            if db_task:
                db_task.status = TaskStatus.BLOCKED
            await session.commit()


def _to_response(run: WorkflowRun) -> WorkflowResponse:
    err = None
    if run.status == "failed" and isinstance(run.state_snapshot, dict):
        err = run.state_snapshot.get("error")
    return WorkflowResponse(
        id=str(run.id),
        task_id=str(run.task_id),
        status=run.status,
        current_node=run.current_node,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        error=err,
    )

"""Workflow execution API routes."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import async_session_factory, get_session
from aeco.models.task import Task, TaskStatus
from aeco.models.workflow import WorkflowRun
from aeco.orchestrator.state import AECOState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# Will be set by main.py after graph is built
_compiled_graph = None


def set_graph(graph):
    global _compiled_graph
    _compiled_graph = graph


class RunWorkflowRequest(BaseModel):
    task_id: str


class WorkflowResponse(BaseModel):
    id: str
    task_id: str
    status: str
    current_node: str
    started_at: str
    completed_at: str | None

    model_config = {"from_attributes": True}


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

    # Create workflow run record
    run = WorkflowRun(task_id=task.id)
    session.add(run)
    task.status = TaskStatus.IN_PROGRESS
    task.workflow_run_id = run.id
    await session.commit()
    await session.refresh(run)

    # Launch workflow in background
    asyncio.create_task(_execute_workflow(run.id, task))

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


async def _execute_workflow(run_id: uuid.UUID, task: Task) -> None:
    """Execute the LangGraph workflow asynchronously."""
    try:
        initial_state: AECOState = {
            "task_id": str(task.id),
            "clickup_task_id": task.clickup_task_id,
            "task_title": task.title,
            "task_description": task.description,
            "status": "todo",
            "messages": [],
            "design_document": None,
            "code_artifacts": [],
            "test_results": None,
            "review_feedback": None,
            "current_agent": None,
            "next_action": None,
            "iteration_count": 0,
            "max_iterations": 5,
            "errors": [],
        }

        logger.info(f"Starting workflow {run_id} for task '{task.title}'")
        final_state = await _compiled_graph.ainvoke(initial_state)
        logger.info(f"Workflow {run_id} completed with status: {final_state.get('status')}")

        # Update workflow run and task
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.status = "completed"
                run.current_node = "done"
                run.state_snapshot = {
                    "status": final_state.get("status"),
                    "iterations": final_state.get("iteration_count"),
                    "files_created": len(final_state.get("code_artifacts", [])),
                }

            db_task = await session.get(Task, task.id)
            if db_task:
                db_task.status = TaskStatus.DONE
                db_task.clickup_task_id = final_state.get("clickup_task_id")

            await session.commit()

    except Exception as e:
        logger.error(f"Workflow {run_id} failed: {e}", exc_info=True)
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if run:
                run.status = "failed"
                run.state_snapshot = {"error": str(e)}
            db_task = await session.get(Task, task.id)
            if db_task:
                db_task.status = TaskStatus.BLOCKED
            await session.commit()


def _to_response(run: WorkflowRun) -> WorkflowResponse:
    return WorkflowResponse(
        id=str(run.id),
        task_id=str(run.task_id),
        status=run.status,
        current_node=run.current_node,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )

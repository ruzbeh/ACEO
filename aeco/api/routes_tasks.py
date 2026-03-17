"""Task API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import get_session
from aeco.models.task import Task, TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    title: str
    description: str = ""


class TaskResponse(BaseModel):
    id: str
    clickup_task_id: str | None
    title: str
    description: str
    status: str
    assigned_agent_id: str | None
    workflow_run_id: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    req: CreateTaskRequest, session: AsyncSession = Depends(get_session)
):
    """Create a new feature request task and trigger workflow."""
    task = Task(
        title=req.title,
        description=req.description,
        status=TaskStatus.TODO,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    # Workflow will be triggered asynchronously via routes_workflows
    return _to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    """Get a task by ID."""
    task = await session.get(Task, uuid.UUID(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_response(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    """List all tasks."""
    result = await session.execute(select(Task).order_by(Task.created_at.desc()))
    tasks = result.scalars().all()
    return [_to_response(t) for t in tasks]


def _to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        clickup_task_id=task.clickup_task_id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        assigned_agent_id=task.assigned_agent_id,
        workflow_run_id=str(task.workflow_run_id) if task.workflow_run_id else None,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )

"""Bidirectional sync between AECO tasks and ClickUp tasks."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.integrations.clickup.client import ClickUpClient
from aeco.integrations.clickup.models import ClickUpTask
from aeco.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

# Map ClickUp statuses to AECO statuses (normalize to lowercase for comparison)
CLICKUP_TO_AECO_STATUS = {
    "to do": TaskStatus.TODO,
    "in progress": TaskStatus.IN_PROGRESS,
    "review": TaskStatus.QA_REVIEW,
    "complete": TaskStatus.DONE,
    "closed": TaskStatus.DONE,
}

AECO_TO_CLICKUP_STATUS = {
    TaskStatus.TODO: "to do",
    TaskStatus.IN_PROGRESS: "in progress",
    TaskStatus.ARCHITECT_DESIGN: "in progress",
    TaskStatus.ENGINEERING: "in progress",
    TaskStatus.QA_REVIEW: "review",
    TaskStatus.DONE: "complete",
    TaskStatus.BLOCKED: "to do",
}


async def sync_task_to_clickup(
    task: Task, client: ClickUpClient, list_id: str
) -> str | None:
    """Create or update a ClickUp task from an AECO task. Returns ClickUp task ID."""
    clickup_status = AECO_TO_CLICKUP_STATUS.get(task.status, "to do")

    if task.clickup_task_id:
        await client.update_task(
            task.clickup_task_id,
            name=task.title,
            description=task.description,
            status=clickup_status,
        )
        return task.clickup_task_id
    else:
        cu_task = await client.create_task(
            list_id=list_id,
            name=task.title,
            description=task.description,
            status=clickup_status,
        )
        return cu_task.id


async def sync_task_from_clickup(
    clickup_task_id: str,
    client: ClickUpClient,
    session: AsyncSession,
) -> Task | None:
    """Update an AECO task from ClickUp. Finds task by clickup_task_id. Returns the AECO task or None."""
    result = await session.execute(
        select(Task).where(Task.clickup_task_id == clickup_task_id)
    )
    aeco_task = result.scalar_one_or_none()
    if not aeco_task:
        return None
    cu_task = await client.get_task(clickup_task_id)
    aeco_task.title = cu_task.name
    aeco_task.description = cu_task.description or ""
    status = (cu_task.status or "").strip().lower()
    aeco_task.status = CLICKUP_TO_AECO_STATUS.get(status, aeco_task.status)
    await session.commit()
    await session.refresh(aeco_task)
    logger.info(f"Synced AECO task {aeco_task.id} from ClickUp {clickup_task_id}")
    return aeco_task


def aeco_task_from_clickup_task(cu_task: ClickUpTask) -> Task:
    """Build an AECO Task model (not persisted) from a ClickUp task."""
    status = (cu_task.status or "").strip().lower()
    aeco_status = CLICKUP_TO_AECO_STATUS.get(status, TaskStatus.TODO)
    return Task(
        title=cu_task.name,
        description=cu_task.description or "",
        status=aeco_status,
        clickup_task_id=cu_task.id,
    )

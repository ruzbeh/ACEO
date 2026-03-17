"""Bidirectional sync between AECO tasks and ClickUp tasks."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from aeco.integrations.clickup.client import ClickUpClient
from aeco.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

# Map ClickUp statuses to AECO statuses
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

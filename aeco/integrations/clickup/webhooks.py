"""ClickUp webhook event processing and execution."""

import logging
from typing import Any

from aeco.api.routes_workflows import trigger_workflow_for_task
from aeco.config import settings
from aeco.db.session import async_session_factory
from aeco.integrations.clickup.client import ClickUpClient
from aeco.integrations.clickup.sync import (
    aeco_task_from_clickup_task,
    sync_task_from_clickup,
)

logger = logging.getLogger(__name__)


async def process_webhook_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process an incoming ClickUp webhook: run the right action and return a result."""
    event_type = event.get("event")
    task_id = event.get("task_id")  # ClickUp task ID (string)

    logger.info(f"ClickUp webhook: event={event_type} task_id={task_id}")

    if not task_id:
        return {"action": "ignore", "reason": "missing task_id"}

    if not settings.clickup_api_token:
        logger.warning("ClickUp API token not set; webhook actions skipped")
        return {"action": "skip", "reason": "clickup_api_token not configured"}

    client = ClickUpClient(settings.clickup_api_token)
    try:
        if event_type == "taskCreated":
            return await _on_task_created(client, task_id)
        if event_type == "taskUpdated":
            return await _on_task_updated(client, task_id)
        if event_type == "taskCommentPosted":
            return await _on_task_comment_posted(client, task_id, event)
        return {"action": "ignore", "event": event_type}
    finally:
        await client.close()


async def _on_task_created(client: ClickUpClient, clickup_task_id: str) -> dict[str, Any]:
    """Create AECO task from ClickUp task and start workflow."""
    try:
        cu_task = await client.get_task(clickup_task_id)
    except Exception as e:
        logger.exception(f"Failed to fetch ClickUp task {clickup_task_id}: {e}")
        return {"action": "create_workflow", "error": str(e), "task_id": clickup_task_id}

    async with async_session_factory() as session:
        aeco_task = aeco_task_from_clickup_task(cu_task)
        session.add(aeco_task)
        await session.commit()
        await session.refresh(aeco_task)
        aeco_id = str(aeco_task.id)
    logger.info(f"Created AECO task {aeco_id} from ClickUp {clickup_task_id}")

    run = await trigger_workflow_for_task(aeco_task.id)
    if run:
        return {
            "action": "create_workflow",
            "aeco_task_id": aeco_id,
            "workflow_run_id": str(run.id),
            "clickup_task_id": clickup_task_id,
        }
    return {
        "action": "create_workflow",
        "aeco_task_id": aeco_id,
        "workflow_run_id": None,
        "clickup_task_id": clickup_task_id,
        "warning": "workflow not started (graph not ready or error)",
    }


async def _on_task_updated(client: ClickUpClient, clickup_task_id: str) -> dict[str, Any]:
    """Sync AECO task from ClickUp."""
    async with async_session_factory() as session:
        try:
            aeco_task = await sync_task_from_clickup(
                clickup_task_id, client, session
            )
        except Exception as e:
            logger.exception(f"Failed to sync from ClickUp {clickup_task_id}: {e}")
            return {"action": "sync_task", "error": str(e), "task_id": clickup_task_id}
    if aeco_task:
        return {
            "action": "sync_task",
            "aeco_task_id": str(aeco_task.id),
            "clickup_task_id": clickup_task_id,
        }
    return {
        "action": "sync_task",
        "aeco_task_id": None,
        "clickup_task_id": clickup_task_id,
        "reason": "no AECO task linked to this ClickUp task",
    }


async def _on_task_comment_posted(
    client: ClickUpClient, clickup_task_id: str, event: dict[str, Any]
) -> dict[str, Any]:
    """Store latest comment on AECO task metadata (minimal processing)."""
    comment_text = (event.get("comment") or {}).get("comment_text") or ""
    if not comment_text:
        return {"action": "process_comment", "task_id": clickup_task_id, "stored": False}

    from sqlalchemy import select

    from aeco.models.task import Task

    async with async_session_factory() as session:
        result = await session.execute(
            select(Task).where(Task.clickup_task_id == clickup_task_id)
        )
        aeco_task = result.scalar_one_or_none()
        if not aeco_task:
            return {
                "action": "process_comment",
                "clickup_task_id": clickup_task_id,
                "stored": False,
                "reason": "no AECO task linked",
            }
        meta = dict(aeco_task.metadata_ or {})
        meta["last_comment"] = comment_text
        aeco_task.metadata_ = meta
        aeco_id = str(aeco_task.id)
        await session.commit()
    logger.info(f"Stored comment on AECO task for ClickUp {clickup_task_id}")
    return {
        "action": "process_comment",
        "aeco_task_id": aeco_id,
        "clickup_task_id": clickup_task_id,
        "stored": True,
    }

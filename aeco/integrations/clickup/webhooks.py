"""ClickUp webhook event processing."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def process_webhook_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process an incoming ClickUp webhook event.

    Returns action to take based on the event type.
    """
    event_type = event.get("event")
    task_id = event.get("task_id")

    logger.info(f"ClickUp webhook: event={event_type} task_id={task_id}")

    match event_type:
        case "taskCreated":
            return {"action": "create_workflow", "task_id": task_id}
        case "taskUpdated":
            return {"action": "sync_task", "task_id": task_id}
        case "taskCommentPosted":
            return {"action": "process_comment", "task_id": task_id}
        case _:
            return {"action": "ignore", "event": event_type}

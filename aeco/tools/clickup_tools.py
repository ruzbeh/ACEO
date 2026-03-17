"""ClickUp operations exposed as tool functions for agents."""

from aeco.config import settings
from aeco.integrations.clickup.client import ClickUpClient

_client: ClickUpClient | None = None


def _get_client() -> ClickUpClient:
    global _client
    if _client is None:
        _client = ClickUpClient(api_token=settings.clickup_api_token)
    return _client


async def clickup_read_task(task_id: str) -> dict:
    """Read a ClickUp task's details."""
    client = _get_client()
    task = await client.get_task(task_id)
    return task.model_dump()


async def clickup_update_task(task_id: str, **fields) -> dict:
    """Update a ClickUp task's fields (status, name, description, etc.)."""
    client = _get_client()
    task = await client.update_task(task_id, **fields)
    return task.model_dump()


async def clickup_create_comment(task_id: str, comment_text: str) -> dict:
    """Post a comment on a ClickUp task."""
    client = _get_client()
    comment = await client.create_comment(task_id, comment_text)
    return comment.model_dump()


async def clickup_create_task(name: str, description: str = "") -> dict:
    """Create a new task in the default ClickUp list."""
    client = _get_client()
    task = await client.create_task(
        list_id=settings.clickup_list_id,
        name=name,
        description=description,
    )
    return task.model_dump()

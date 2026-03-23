"""ClickUp operations exposed as tool functions for agents."""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from aeco.config import settings
from aeco.integrations.clickup.client import ClickUpClient

logger = logging.getLogger(__name__)

_client: Optional[ClickUpClient] = None

# ClickUp task IDs are short alphanumeric (e.g. 9hz). AECO task_id is a UUID — do not pass it to ClickUp.
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _get_client() -> Optional[ClickUpClient]:
    if not (settings.clickup_api_token and settings.clickup_api_token.strip()):
        return None
    global _client
    if _client is None:
        _client = ClickUpClient(api_token=settings.clickup_api_token)
    return _client


async def clickup_read_task(task_id: str) -> dict:
    """Read a ClickUp task's details. task_id must be the ClickUp task ID (short, e.g. 9hz), not an internal AECO task ID (UUID). Use clickup_list_tasks to get ClickUp task IDs from a list."""
    if _UUID_PATTERN.match(task_id.strip()):
        return {
            "error": "clickup_read_task expects a ClickUp task ID (short alphanumeric, e.g. from the task URL or from clickup_list_tasks), not an internal AECO task_id (UUID). Use clickup_list_tasks to list tasks in your list and use their 'id' field.",
        }
    client = _get_client()
    if not client:
        return {"error": "ClickUp not configured. Set CLICKUP_API_TOKEN in .env (ClickUp → Settings → Apps → API Token)."}
    try:
        task = await client.get_task(task_id)
        return task.model_dump()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning("ClickUp 401: token invalid or expired. Set a valid CLICKUP_API_TOKEN in .env.")
            return {"error": "ClickUp API 401 Unauthorized. Set a valid CLICKUP_API_TOKEN in .env (ClickUp → Settings → Apps → API Token)."}
        if e.response.status_code == 404:
            return {
                "error": "ClickUp task not found (404). Ensure the task_id is the ClickUp task ID (from the task URL or clickup_list_tasks), not an internal ID.",
            }
        raise
    except Exception as e:
        logger.warning("ClickUp read_task failed: %s", e)
        return {"error": str(e)}


async def clickup_update_task(task_id: str, **fields) -> dict:
    """Update a ClickUp task's fields (status, name, description, etc.)."""
    client = _get_client()
    if not client:
        return {"error": "ClickUp not configured. Set CLICKUP_API_TOKEN in .env."}
    try:
        task = await client.update_task(task_id, **fields)
        return task.model_dump()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"error": "ClickUp API 401. Set a valid CLICKUP_API_TOKEN in .env."}
        raise
    except Exception as e:
        return {"error": str(e)}


async def clickup_create_comment(task_id: str, comment_text: str) -> dict:
    """Post a comment on a ClickUp task."""
    client = _get_client()
    if not client:
        return {"error": "ClickUp not configured. Set CLICKUP_API_TOKEN in .env."}
    try:
        comment = await client.create_comment(task_id, comment_text)
        return comment.model_dump()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"error": "ClickUp API 401. Set a valid CLICKUP_API_TOKEN in .env."}
        raise
    except Exception as e:
        return {"error": str(e)}


async def clickup_create_task(name: str, description: str = "") -> dict:
    """Create a new task in the default ClickUp list."""
    client = _get_client()
    if not client:
        return {"error": "ClickUp not configured. Set CLICKUP_API_TOKEN and CLICKUP_LIST_ID in .env."}
    if not (settings.clickup_list_id and settings.clickup_list_id.strip()):
        return {"error": "CLICKUP_LIST_ID not set in .env."}
    try:
        task = await client.create_task(
            list_id=settings.clickup_list_id,
            name=name,
            description=description,
        )
        return task.model_dump()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"error": "ClickUp API 401. Set a valid CLICKUP_API_TOKEN in .env."}
        raise
    except Exception as e:
        return {"error": str(e)}

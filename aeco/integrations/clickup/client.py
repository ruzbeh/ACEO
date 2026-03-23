import logging
from typing import Any

import httpx

from aeco.integrations.clickup.models import ClickUpComment, ClickUpTask

logger = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"


class ClickUpClient:
    """Async HTTP client for ClickUp API v2."""

    def __init__(self, api_token: str) -> None:
        self._headers = {
            "Authorization": api_token,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=BASE_URL, headers=self._headers, timeout=30.0
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        response = await self._client.request(method, path, **kwargs)
        if response.status_code == 401:
            raise httpx.HTTPStatusError(
                "ClickUp API returned 401 Unauthorized. "
                "Check CLICKUP_API_TOKEN in .env — use a valid token from ClickUp → Settings → Apps → API Token.",
                request=response.request,
                response=response,
            )
        response.raise_for_status()
        return response.json()

    # Tasks
    async def create_task(
        self, list_id: str, name: str, description: str = "", **kwargs: Any
    ) -> ClickUpTask:
        data = {"name": name, "description": description, **kwargs}
        result = await self._request("POST", f"/list/{list_id}/task", json=data)
        return ClickUpTask(**result)

    async def get_task(self, task_id: str) -> ClickUpTask:
        result = await self._request("GET", f"/task/{task_id}")
        return ClickUpTask(**result)

    async def update_task(self, task_id: str, **fields: Any) -> ClickUpTask:
        result = await self._request("PUT", f"/task/{task_id}", json=fields)
        return ClickUpTask(**result)

    # Comments
    async def create_comment(
        self, task_id: str, comment_text: str
    ) -> ClickUpComment:
        data = {"comment_text": comment_text}
        result = await self._request(
            "POST", f"/task/{task_id}/comment", json=data
        )
        return ClickUpComment(
            id=str(result.get("id", "")),
            comment_text=comment_text,
        )

    async def get_comments(self, task_id: str) -> list[ClickUpComment]:
        result = await self._request("GET", f"/task/{task_id}/comment")
        return [
            ClickUpComment(
                id=str(c.get("id", "")),
                comment_text=c.get("comment_text", ""),
                user=c.get("user"),
                date=c.get("date"),
            )
            for c in result.get("comments", [])
        ]

    # Lists
    async def get_list_tasks(self, list_id: str) -> list[ClickUpTask]:
        result = await self._request("GET", f"/list/{list_id}/task")
        return [ClickUpTask(**t) for t in result.get("tasks", [])]

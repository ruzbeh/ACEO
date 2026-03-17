"""Webhook receiver for ClickUp events."""

import logging
from typing import Any

from fastapi import APIRouter, Request

from aeco.integrations.clickup.webhooks import process_webhook_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/clickup")
async def clickup_webhook(request: Request) -> dict[str, Any]:
    """Receive and process ClickUp webhook events."""
    body = await request.json()
    result = await process_webhook_event(body)
    logger.info(f"Webhook processed: {result}")
    return {"status": "ok", "result": result}

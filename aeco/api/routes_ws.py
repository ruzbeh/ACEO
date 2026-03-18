"""WebSocket endpoint for real-time event streaming."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aeco.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws")
async def ws_events(websocket: WebSocket):
    """Stream real-time events to connected clients.

    Clients can optionally send a JSON filter message after connecting:
        {"subscribe": ["initiative.*", "agent.*"]}

    If no filter is sent, all events are forwarded.
    """
    await websocket.accept()
    queue = event_bus.subscribe()
    filters: list[str] = []

    logger.info("WebSocket client connected (%d total)", event_bus.subscriber_count)

    try:
        # Start a background task to check for filter messages from client
        async def _read_filters():
            nonlocal filters
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                        if "subscribe" in msg and isinstance(msg["subscribe"], list):
                            filters = msg["subscribe"]
                            logger.debug("WebSocket client set filters: %s", filters)
                    except (json.JSONDecodeError, KeyError):
                        pass
            except WebSocketDisconnect:
                pass

        reader_task = asyncio.create_task(_read_filters())

        while True:
            event = await queue.get()

            # Apply filters if set
            if filters and not _matches_filter(event.get("type", ""), filters):
                continue

            await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        reader_task.cancel()
        event_bus.unsubscribe(queue)
        logger.info("WebSocket client disconnected (%d remaining)", event_bus.subscriber_count)


def _matches_filter(event_type: str, filters: list[str]) -> bool:
    """Check if an event type matches any of the filter patterns.

    Supports wildcard prefix matching: "initiative.*" matches "initiative.phase_changed".
    Exact match also works: "agent.completed" matches "agent.completed".
    """
    for pattern in filters:
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if event_type.startswith(prefix + "."):
                return True
        elif event_type == pattern:
            return True
    return False

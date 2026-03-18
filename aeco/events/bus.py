"""In-process async event bus for real-time notifications.

All AECO nodes and agents can emit events. WebSocket connections subscribe
to receive them. Uses asyncio.Queue per subscriber with backpressure
(oldest messages dropped when queue is full).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 500


class EventBus:
    """Async pub/sub event bus.

    Thread-safe for use across coroutines. Each subscriber gets its own
    asyncio.Queue. If a subscriber's queue is full, the oldest message
    is dropped to prevent backpressure from blocking emitters.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber. Returns a Queue to read events from."""
        q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers.add(q)
        logger.debug("EventBus: subscriber added (%d total)", len(self._subscribers))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber."""
        self._subscribers.discard(q)
        logger.debug("EventBus: subscriber removed (%d total)", len(self._subscribers))

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Broadcast an event to all subscribers. Non-blocking, fire-and-forget."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload or {},
        }

        for q in list(self._subscribers):
            if q.full():
                # Drop oldest to make room
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Shouldn't happen after drop, but be safe

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

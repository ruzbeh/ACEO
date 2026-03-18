"""Tests for the async event bus."""
from __future__ import annotations

import asyncio

import pytest

from aeco.events.bus import EventBus


@pytest.mark.asyncio
async def test_emit_no_subscribers():
    """Emit with no subscribers should not raise."""
    bus = EventBus()
    await bus.emit("test.event", {"key": "value"})


@pytest.mark.asyncio
async def test_single_subscriber_receives_event():
    bus = EventBus()
    q = bus.subscribe()

    await bus.emit("test.event", {"hello": "world"})

    event = q.get_nowait()
    assert event["type"] == "test.event"
    assert event["data"]["hello"] == "world"
    assert "timestamp" in event


@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    q3 = bus.subscribe()

    await bus.emit("multi.test", {"n": 42})

    for q in (q1, q2, q3):
        event = q.get_nowait()
        assert event["type"] == "multi.test"
        assert event["data"]["n"] == 42


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    q = bus.subscribe()

    await bus.emit("before.unsub", {})
    assert not q.empty()

    bus.unsubscribe(q)
    # Clear the queue
    while not q.empty():
        q.get_nowait()

    await bus.emit("after.unsub", {})
    assert q.empty()


@pytest.mark.asyncio
async def test_unsubscribe_idempotent():
    """Unsubscribing a non-existent queue should not raise."""
    bus = EventBus()
    q = asyncio.Queue()
    bus.unsubscribe(q)  # Never subscribed — should be fine


@pytest.mark.asyncio
async def test_backpressure_drops_oldest():
    """When queue is full, oldest message is dropped to make room."""
    bus = EventBus()
    q = bus.subscribe()

    # Fill the queue
    for i in range(500):
        await bus.emit("fill", {"i": i})

    assert q.full()

    # Emit one more — should drop oldest
    await bus.emit("overflow", {"i": 500})

    # First message should now be i=1 (i=0 was dropped)
    first = q.get_nowait()
    assert first["data"]["i"] == 1


@pytest.mark.asyncio
async def test_subscriber_count():
    bus = EventBus()
    assert bus.subscriber_count == 0

    q1 = bus.subscribe()
    assert bus.subscriber_count == 1

    q2 = bus.subscribe()
    assert bus.subscriber_count == 2

    bus.unsubscribe(q1)
    assert bus.subscriber_count == 1

    bus.unsubscribe(q2)
    assert bus.subscriber_count == 0


@pytest.mark.asyncio
async def test_emit_with_no_payload():
    bus = EventBus()
    q = bus.subscribe()

    await bus.emit("no.payload")

    event = q.get_nowait()
    assert event["data"] == {}

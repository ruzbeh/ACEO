"""Telemetry tools for ingesting and querying product metrics."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def telemetry_ingest(
    metric_name: str,
    value: float,
    product: str | None = None,
    source: str | None = None,
    dimensions: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict:
    """Ingest a single telemetry event.

    Args:
        metric_name: Name of the metric (e.g. "conversion_rate", "mrr", "error_rate").
        value: Numeric metric value.
        product: Product name (e.g. "headshot_ai").
        source: Data source (e.g. "stripe", "facebook", "manual").
        dimensions: Additional dimensions as key-value pairs.
        timestamp: ISO timestamp (defaults to now).

    Returns:
        Confirmation with event ID.
    """
    from aeco.models.telemetry import TelemetryEvent

    ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now(timezone.utc)

    async with async_session_factory() as session:
        event = TelemetryEvent(
            id=uuid.uuid4(),
            metric_name=metric_name,
            value=value,
            product=product,
            source=source,
            dimensions=dimensions or {},
            timestamp=ts,
        )
        session.add(event)
        await session.commit()

    return {
        "status": "ingested",
        "event_id": str(event.id),
        "metric_name": metric_name,
        "value": value,
    }


async def telemetry_ingest_batch(events: list[dict]) -> dict:
    """Ingest multiple telemetry events at once.

    Args:
        events: List of event dicts with keys: metric_name, value, product, source, dimensions, timestamp.

    Returns:
        Count of ingested events.
    """
    from aeco.models.telemetry import TelemetryEvent

    async with async_session_factory() as session:
        for evt in events:
            ts = (
                datetime.fromisoformat(evt["timestamp"])
                if evt.get("timestamp")
                else datetime.now(timezone.utc)
            )
            event = TelemetryEvent(
                id=uuid.uuid4(),
                metric_name=evt["metric_name"],
                value=evt["value"],
                product=evt.get("product"),
                source=evt.get("source"),
                dimensions=evt.get("dimensions", {}),
                timestamp=ts,
            )
            session.add(event)
        await session.commit()

    return {"status": "ingested", "count": len(events)}


async def telemetry_query(
    metric_name: str,
    product: str | None = None,
    days: int = 7,
    aggregation: str = "avg",
    group_by: str | None = None,
) -> dict:
    """Query telemetry data with aggregations.

    Args:
        metric_name: Metric to query.
        product: Filter by product (optional).
        days: Look-back period in days (default 7).
        aggregation: One of "avg", "sum", "count", "min", "max", "latest", "trend".
        group_by: Group by a dimension key (optional).

    Returns:
        Aggregated metric data.
    """
    from aeco.models.telemetry import TelemetryEvent

    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        if aggregation == "latest":
            return await _query_latest(session, metric_name, product, since)
        elif aggregation == "trend":
            return await _query_trend(session, metric_name, product, since)
        else:
            return await _query_aggregate(
                session, metric_name, product, since, aggregation
            )


async def _query_aggregate(
    session: AsyncSession,
    metric_name: str,
    product: str | None,
    since: datetime,
    aggregation: str,
) -> dict:
    from aeco.models.telemetry import TelemetryEvent

    agg_funcs = {
        "avg": func.avg(TelemetryEvent.value),
        "sum": func.sum(TelemetryEvent.value),
        "count": func.count(TelemetryEvent.id),
        "min": func.min(TelemetryEvent.value),
        "max": func.max(TelemetryEvent.value),
    }
    agg_fn = agg_funcs.get(aggregation, func.avg(TelemetryEvent.value))

    conditions = [
        TelemetryEvent.metric_name == metric_name,
        TelemetryEvent.timestamp >= since,
    ]
    if product:
        conditions.append(TelemetryEvent.product == product)

    stmt = select(agg_fn.label("result")).where(and_(*conditions))
    result = await session.execute(stmt)
    row = result.one_or_none()

    count_stmt = select(func.count(TelemetryEvent.id)).where(and_(*conditions))
    count_result = await session.execute(count_stmt)
    count = count_result.scalar() or 0

    return {
        "metric_name": metric_name,
        "product": product,
        "aggregation": aggregation,
        "value": round(row.result, 4) if row and row.result is not None else None,
        "data_points": count,
        "period_days": (datetime.now(timezone.utc) - since).days,
    }


async def _query_latest(
    session: AsyncSession,
    metric_name: str,
    product: str | None,
    since: datetime,
) -> dict:
    from aeco.models.telemetry import TelemetryEvent

    conditions = [
        TelemetryEvent.metric_name == metric_name,
        TelemetryEvent.timestamp >= since,
    ]
    if product:
        conditions.append(TelemetryEvent.product == product)

    stmt = (
        select(TelemetryEvent)
        .where(and_(*conditions))
        .order_by(TelemetryEvent.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        return {"metric_name": metric_name, "value": None, "timestamp": None}

    return {
        "metric_name": metric_name,
        "product": product,
        "aggregation": "latest",
        "value": event.value,
        "timestamp": event.timestamp.isoformat(),
        "dimensions": event.dimensions,
    }


async def _query_trend(
    session: AsyncSession,
    metric_name: str,
    product: str | None,
    since: datetime,
) -> dict:
    """Simple trend: compare first half vs second half of the period."""
    from aeco.models.telemetry import TelemetryEvent

    midpoint = since + (datetime.now(timezone.utc) - since) / 2

    conditions_base = [
        TelemetryEvent.metric_name == metric_name,
        TelemetryEvent.timestamp >= since,
    ]
    if product:
        conditions_base.append(TelemetryEvent.product == product)

    # First half average
    first_half = select(func.avg(TelemetryEvent.value).label("avg")).where(
        and_(*conditions_base, TelemetryEvent.timestamp < midpoint)
    )
    # Second half average
    second_half = select(func.avg(TelemetryEvent.value).label("avg")).where(
        and_(*conditions_base, TelemetryEvent.timestamp >= midpoint)
    )

    r1 = await session.execute(first_half)
    r2 = await session.execute(second_half)
    avg1 = r1.scalar()
    avg2 = r2.scalar()

    if avg1 and avg2 and avg1 != 0:
        change_pct = round((avg2 - avg1) / avg1 * 100, 2)
        direction = "up" if change_pct > 0 else "down" if change_pct < 0 else "flat"
    else:
        change_pct = 0
        direction = "insufficient_data"

    return {
        "metric_name": metric_name,
        "product": product,
        "aggregation": "trend",
        "first_half_avg": round(avg1, 4) if avg1 else None,
        "second_half_avg": round(avg2, 4) if avg2 else None,
        "change_pct": change_pct,
        "direction": direction,
    }

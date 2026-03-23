"""API routes for telemetry ingestion and querying."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aeco.tools.telemetry_tools import (
    telemetry_ingest,
    telemetry_ingest_batch,
    telemetry_query,
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class IngestEventRequest(BaseModel):
    metric_name: str
    value: float
    product: Optional[str] = None
    source: Optional[str] = None
    dimensions: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class IngestBatchRequest(BaseModel):
    events: List[IngestEventRequest]


class QueryRequest(BaseModel):
    metric_name: str
    product: Optional[str] = None
    days: int = 7
    aggregation: str = "avg"
    group_by: Optional[str] = None


@router.post("/events")
async def ingest_event(req: IngestEventRequest):
    result = await telemetry_ingest(
        metric_name=req.metric_name,
        value=req.value,
        product=req.product,
        source=req.source,
        dimensions=req.dimensions,
        timestamp=req.timestamp,
    )
    return result


@router.post("/events/batch")
async def ingest_batch(req: IngestBatchRequest):
    events = [e.model_dump() for e in req.events]
    result = await telemetry_ingest_batch(events)
    return result


@router.post("/query")
async def query_metrics(req: QueryRequest):
    result = await telemetry_query(
        metric_name=req.metric_name,
        product=req.product,
        days=req.days,
        aggregation=req.aggregation,
        group_by=req.group_by,
    )
    return result


@router.get("/metrics")
async def list_available_metrics():
    """List distinct metric names in the telemetry store."""
    from sqlalchemy import select, distinct

    from aeco.db.session import async_session_factory
    from aeco.models.telemetry import TelemetryEvent

    async with async_session_factory() as session:
        stmt = select(distinct(TelemetryEvent.metric_name)).order_by(
            TelemetryEvent.metric_name
        )
        result = await session.execute(stmt)
        metrics = [row[0] for row in result]

    return {"metrics": metrics}

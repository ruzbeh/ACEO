"""Postgres-backed structured memory for persisting workflow knowledge."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(100), index=True)
    key: Mapped[str] = mapped_column(String(500), index=True)
    value: Mapped[dict] = mapped_column(JSON)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MemoryStore:
    """Structured key-value memory backed by Postgres."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def store(
        self, category: str, key: str, value: dict, metadata: Optional[dict] = None
    ) -> MemoryEntry:
        async with self._session_factory() as session:
            session: AsyncSession
            # Upsert: update if exists, create if not
            result = await session.execute(
                select(MemoryEntry).where(
                    MemoryEntry.category == category, MemoryEntry.key == key
                )
            )
            entry = result.scalar_one_or_none()
            if entry:
                entry.value = value
                if metadata:
                    entry.metadata_ = metadata
            else:
                entry = MemoryEntry(
                    category=category,
                    key=key,
                    value=value,
                    metadata_=metadata or {},
                )
                session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def retrieve(self, category: str, key: str) -> dict | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MemoryEntry).where(
                    MemoryEntry.category == category, MemoryEntry.key == key
                )
            )
            entry = result.scalar_one_or_none()
            return entry.value if entry else None

    async def list_by_category(self, category: str) -> list[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MemoryEntry)
                .where(MemoryEntry.category == category)
                .order_by(MemoryEntry.updated_at.desc())
            )
            return [
                {"key": e.key, "value": e.value, "updated_at": e.updated_at.isoformat()}
                for e in result.scalars().all()
            ]

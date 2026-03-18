#!/usr/bin/env python3
"""Print recent audit log entries. Run from project root with project env active."""
import asyncio
import sys

from aeco.db.session import async_session_factory
from aeco.models.audit import AuditLogEntry
from sqlalchemy import select


async def main(limit: int = 20) -> None:
    async with async_session_factory() as session:
        r = await session.execute(
            select(AuditLogEntry)
            .order_by(AuditLogEntry.timestamp.desc())
            .limit(limit)
        )
        rows = list(r.scalars())
    if not rows:
        print("No audit log entries found.")
        return
    print(f"Latest {len(rows)} audit log entries:\n")
    for e in rows:
        print(f"  {e.timestamp}  {e.agent_id}  {e.action}  success={e.success}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    asyncio.run(main(limit=n))

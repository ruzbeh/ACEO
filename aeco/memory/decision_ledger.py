"""Decision Ledger store: persist and query decisions with assumptions and outcomes."""
from __future__ import annotations

import uuid
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.models.decision_ledger import DecisionRecord


class DecisionLedgerStore:
    """Async store for the decision ledger."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        category: str,
        agent_id: str,
        decision: str,
        reasoning: str = "",
        assumptions: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        confidence: float = 0.0,
        alternatives_considered: Optional[List[str]] = None,
        initiative_id: Optional[uuid.UUID] = None,
        task_id: Optional[uuid.UUID] = None,
        workflow_run_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict] = None,
    ) -> DecisionRecord:
        entry = DecisionRecord(
            category=category,
            agent_id=agent_id,
            decision=decision,
            reasoning=reasoning,
            assumptions=assumptions or [],
            evidence_refs=evidence_refs or [],
            risks=risks or [],
            confidence=confidence,
            alternatives_considered=alternatives_considered or [],
            initiative_id=initiative_id,
            task_id=task_id,
            workflow_run_id=workflow_run_id,
            metadata_=metadata or {},
        )
        async with self._session_factory() as session:
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def record_outcome(
        self,
        decision_id: uuid.UUID,
        outcome: str,
        assumptions_validated: Optional[dict] = None,
        lessons_learned: str = "",
    ) -> Optional[DecisionRecord]:
        async with self._session_factory() as session:
            entry = await session.get(DecisionRecord, decision_id)
            if not entry:
                return None
            entry.outcome = outcome
            entry.assumptions_validated = assumptions_validated
            entry.lessons_learned = lessons_learned
            await session.commit()
            await session.refresh(entry)
            return entry

    async def get_by_initiative(self, initiative_id: uuid.UUID) -> List[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(DecisionRecord)
                .where(DecisionRecord.initiative_id == initiative_id)
                .order_by(DecisionRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            return [self._to_dict(r) for r in result.scalars()]

    async def get_by_category(
        self, category: str, limit: int = 20
    ) -> List[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(DecisionRecord)
                .where(DecisionRecord.category == category)
                .order_by(DecisionRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._to_dict(r) for r in result.scalars()]

    async def get_recent(self, limit: int = 20) -> List[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(DecisionRecord)
                .order_by(DecisionRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._to_dict(r) for r in result.scalars()]

    @staticmethod
    def _to_dict(r: DecisionRecord) -> dict:
        return {
            "id": str(r.id),
            "category": r.category,
            "agent_id": r.agent_id,
            "initiative_id": str(r.initiative_id) if r.initiative_id else None,
            "decision": r.decision,
            "reasoning": r.reasoning,
            "assumptions": r.assumptions,
            "evidence_refs": r.evidence_refs,
            "risks": r.risks,
            "confidence": r.confidence,
            "alternatives_considered": r.alternatives_considered,
            "outcome": r.outcome,
            "assumptions_validated": r.assumptions_validated,
            "lessons_learned": r.lessons_learned,
            "created_at": r.created_at.isoformat(),
        }

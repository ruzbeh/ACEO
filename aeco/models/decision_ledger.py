"""Decision Ledger: records WHY decisions were made, by whom, on what assumptions.

Every major decision in the system (architecture choices, initiative verdicts, budget
approvals, routing decisions) gets a ledger entry. This enables postmortems, learning,
and assumption validation. See docs/architecture-vision.md section 9.
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class DecisionCategory(str, enum.Enum):
    ARCHITECTURE = "architecture"
    INITIATIVE = "initiative"
    BUDGET = "budget"
    ROUTING = "routing"
    ROLLOUT = "rollout"
    EVALUATION = "evaluation"
    HIRING = "hiring"


class DecisionRecord(Base):
    """A record of a decision with explicit assumptions, evidence, and outcome."""

    __tablename__ = "decision_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), index=True)
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    initiative_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    workflow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)

    decision: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    alternatives_considered: Mapped[list] = mapped_column(JSON, default=list)

    # Outcome tracking (filled in later during evaluation)
    outcome: Mapped[Optional[str]] = mapped_column(Text)
    assumptions_validated: Mapped[Optional[dict]] = mapped_column(JSON)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text)

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

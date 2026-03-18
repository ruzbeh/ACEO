"""Initiative as the top-level unit of work for the product company simulator.

An initiative is done only when: shipped, telemetry live, metrics collected,
outcome evaluated, learnings written back, and next action chosen (expand / iterate / kill).
See docs/architecture-vision.md.
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class InitiativeStatus(str, enum.Enum):
    """Lifecycle state of an initiative."""

    DRAFT = "draft"  # Spec/PRD being written
    PLANNING = "planning"  # Technical design, task graph
    EXECUTING = "executing"  # Implementation in progress
    IN_REVIEW = "in_review"  # QA, security, critic
    ROLLING_OUT = "rolling_out"  # Staged rollout
    MEASURING = "measuring"  # Evaluation window
    CLOSED = "closed"  # Verdict applied


class InitiativeVerdict(str, enum.Enum):
    """Final or intermediate verdict after evaluation."""

    PENDING = "pending"  # Not yet evaluated
    SCALE = "scale"  # Expand
    ITERATE = "iterate"  # Refine and re-measure
    KILL = "kill"  # Stop and learn


class Initiative(Base):
    """Product initiative: goal, hypothesis, metrics, task graph, rollout, evaluation."""

    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    goal: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    north_star_metric: Mapped[Optional[str]] = mapped_column(String(255))  # e.g. "onboarding_conversion"
    local_metric: Mapped[Optional[str]] = mapped_column(String(255))  # e.g. "signup_step_2_completion"
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    non_goals: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(50),
        default=InitiativeStatus.DRAFT.value,
    )
    verdict: Mapped[str] = mapped_column(
        String(50),
        default=InitiativeVerdict.PENDING.value,
    )
    evaluation_window_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rollout_plan: Mapped[dict] = mapped_column(JSON, default=dict)  # stages, rollback triggers
    task_graph_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # for audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

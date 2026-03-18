"""PortfolioCycle — persists portfolio run state across server restarts.

Each portfolio run creates a PortfolioCycle row. State is serialized as JSON
and updated as the run progresses. On server restart, completed runs are
loaded from DB; running runs are marked as failed.
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class PortfolioCycleStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class PortfolioCycle(Base):
    """Persisted portfolio run with full state snapshot."""

    __tablename__ = "portfolio_cycles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Run metadata
    status: Mapped[str] = mapped_column(String(20), default=PortfolioCycleStatus.RUNNING.value, index=True)
    current_phase: Mapped[str] = mapped_column(String(50), default="starting")

    # Goals & config
    company_goals: Mapped[list] = mapped_column(JSON, default=list)
    max_cycles: Mapped[int] = mapped_column(Integer, default=2)
    workspace_path: Mapped[Optional[str]] = mapped_column(String(1000))

    # Budget
    total_budget: Mapped[float] = mapped_column(Float, default=0.0)
    budget_spent: Mapped[float] = mapped_column(Float, default=0.0)
    budget_remaining: Mapped[float] = mapped_column(Float, default=0.0)

    # Progress counters
    cycle_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_found: Mapped[int] = mapped_column(Integer, default=0)
    initiatives_funded: Mapped[int] = mapped_column(Integer, default=0)
    initiatives_killed: Mapped[int] = mapped_column(Integer, default=0)
    execution_results_count: Mapped[int] = mapped_column(Integer, default=0)

    # Full state snapshot (JSON) — opportunities, decisions, results, messages, errors
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def update_from_state(self, state: dict) -> None:
        """Update counters and snapshot from portfolio workflow state."""
        self.current_phase = state.get("current_phase", self.current_phase)
        self.cycle_count = state.get("cycle_count", self.cycle_count)
        self.budget_spent = state.get("budget_spent", self.budget_spent)
        self.budget_remaining = state.get("budget_remaining", self.budget_remaining)
        self.opportunities_found = len(state.get("opportunities", []))
        self.initiatives_funded = len(state.get("funded_initiatives", []))
        self.initiatives_killed = len(state.get("killed_initiatives", []))
        self.execution_results_count = len(state.get("execution_results", []))
        self.state_snapshot = {
            "company_goals": state.get("company_goals", []),
            "opportunities": state.get("opportunities", [])[-20:],
            "portfolio_decisions": state.get("portfolio_decisions", []),
            "funded_initiatives": state.get("funded_initiatives", []),
            "killed_initiatives": state.get("killed_initiatives", []),
            "execution_results": state.get("execution_results", []),
            "messages": state.get("messages", [])[-50:],
            "errors": state.get("errors", []),
        }
        self.updated_at = datetime.now(timezone.utc)

    def to_list_item(self) -> dict:
        """Serialize for the list endpoint."""
        return {
            "portfolio_id": str(self.id),
            "status": self.status,
            "current_phase": self.current_phase,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "cycle_count": self.cycle_count,
            "max_cycles": self.max_cycles,
        }

    def to_status_dict(self) -> dict:
        """Full status for the detail endpoint."""
        snap = self.state_snapshot or {}
        return {
            "portfolio_id": str(self.id),
            "current_phase": self.current_phase,
            "cycle_count": self.cycle_count,
            "max_cycles": self.max_cycles,
            "budget_spent": self.budget_spent,
            "budget_remaining": self.budget_remaining,
            "total_budget": self.total_budget,
            "opportunities_found": self.opportunities_found,
            "initiatives_funded": self.initiatives_funded,
            "initiatives_killed": self.initiatives_killed,
            "execution_results": self.execution_results_count,
            "status": self.status,
            "company_goals": snap.get("company_goals", self.company_goals),
            "opportunities": snap.get("opportunities", []),
            "portfolio_decisions": snap.get("portfolio_decisions", []),
            "results": snap.get("execution_results", []),
            "errors": snap.get("errors", []),
            "messages": snap.get("messages", []),
        }

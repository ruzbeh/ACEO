"""Approval queue model for human-in-the-loop decisions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.sqlite import JSON

from aeco.db.base import Base


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(Base):
    """A decision that requires human approval before execution."""

    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), nullable=True)
    initiative_id = Column(String(36), nullable=True)
    initiative_title = Column(String(500), nullable=False)
    action = Column(String(50), nullable=False)  # fund, kill, scale
    reasoning = Column(Text, nullable=False, default="")
    allocated_budget = Column(Float, nullable=False, default=0.0)
    blast_radius = Column(String(50), nullable=False, default="low")
    requested_by = Column(String(100), nullable=False, default="ceo_director")
    status = Column(String(20), nullable=False, default=ApprovalStatus.PENDING.value)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

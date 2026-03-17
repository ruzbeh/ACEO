import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from aeco.db.base import Base


class MessageType(str, enum.Enum):
    TASK_ASSIGNMENT = "task_assignment"
    DESIGN_DOCUMENT = "design_document"
    CODE_ARTIFACT = "code_artifact"
    CODE_REVIEW = "code_review"
    BUG_REPORT = "bug_report"
    STATUS_UPDATE = "status_update"
    APPROVAL = "approval"
    REJECTION = "rejection"


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(index=True)
    sender_agent_id: Mapped[str] = mapped_column(String(100))
    recipient_agent_id: Mapped[str] = mapped_column(String(100))
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    task_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

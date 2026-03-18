"""Tests for SQLAlchemy model instantiation and enum values."""

import uuid
from datetime import datetime, timezone

from aeco.models.audit import AuditLogEntry
from aeco.models.message import AgentMessage, MessageType
from aeco.models.task import Task, TaskStatus
from aeco.models.workflow import WorkflowRun
from aeco.memory.store import MemoryEntry


class TestTaskStatusEnum:
    def test_all_expected_values(self) -> None:
        expected = {"todo", "in_progress", "architect_design", "engineering", "qa_review", "done", "blocked"}
        actual = {member.value for member in TaskStatus}
        assert actual == expected

    def test_str_mixin(self) -> None:
        assert str(TaskStatus.TODO) == "TaskStatus.TODO"
        assert TaskStatus.DONE.value == "done"


class TestMessageTypeEnum:
    def test_all_expected_values(self) -> None:
        expected = {
            "task_assignment",
            "design_document",
            "code_artifact",
            "code_review",
            "bug_report",
            "status_update",
            "approval",
            "rejection",
        }
        actual = {member.value for member in MessageType}
        assert actual == expected

    def test_str_mixin(self) -> None:
        assert MessageType.APPROVAL.value == "approval"


class TestTaskModel:
    def test_instantiate_with_defaults(self) -> None:
        task = Task(
            id=uuid.uuid4(),
            title="Implement feature X",
        )
        assert task.title == "Implement feature X"
        assert task.__tablename__ == "tasks"

    def test_instantiate_with_all_fields(self) -> None:
        uid = uuid.uuid4()
        wf_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        task = Task(
            id=uid,
            clickup_task_id="abc123",
            title="Full task",
            description="A detailed description",
            status=TaskStatus.IN_PROGRESS,
            assigned_agent_id="backend_engineer",
            workflow_run_id=wf_id,
            metadata_={"priority": "high"},
            created_at=now,
            updated_at=now,
        )
        assert task.id == uid
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.metadata_ == {"priority": "high"}


class TestAgentMessageModel:
    def test_instantiate(self) -> None:
        msg = AgentMessage(
            id=uuid.uuid4(),
            workflow_run_id=uuid.uuid4(),
            sender_agent_id="coo_orchestrator",
            recipient_agent_id="chief_architect",
            message_type=MessageType.TASK_ASSIGNMENT,
            payload={"task": "design"},
            task_id=uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        assert msg.__tablename__ == "agent_messages"
        assert msg.message_type == MessageType.TASK_ASSIGNMENT


class TestWorkflowRunModel:
    def test_instantiate(self) -> None:
        run = WorkflowRun(
            id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            status="running",
            current_node="intake",
            state_snapshot={"step": 1},
            started_at=datetime.now(timezone.utc),
        )
        assert run.__tablename__ == "workflow_runs"
        assert run.current_node == "intake"


class TestAuditLogEntryModel:
    def test_instantiate(self) -> None:
        entry = AuditLogEntry(
            id=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            agent_id="qa_engineer",
            action="code_review",
            success=True,
        )
        assert entry.__tablename__ == "audit_log"
        assert entry.agent_id == "qa_engineer"

    def test_optional_fields_default_to_none(self) -> None:
        entry = AuditLogEntry(
            id=uuid.uuid4(),
            agent_id="x",
            action="y",
        )
        assert entry.llm_provider is None
        assert entry.tokens_used is None
        assert entry.error_message is None


class TestMemoryEntryModel:
    def test_instantiate(self) -> None:
        entry = MemoryEntry(
            id=uuid.uuid4(),
            category="decisions",
            key="arch-v1",
            value={"choice": "event-driven"},
            metadata_={"author": "chief_architect"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert entry.__tablename__ == "memory_entries"
        assert entry.value == {"choice": "event-driven"}

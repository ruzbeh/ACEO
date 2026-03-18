"""Initial schema – create tasks, agent_messages, workflow_runs, audit_log, memory_entries

Revision ID: 001
Revises: None
Create Date: 2026-03-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types referenced by multiple tables
task_status_enum = sa.Enum(
    "todo",
    "in_progress",
    "architect_design",
    "engineering",
    "qa_review",
    "done",
    "blocked",
    name="taskstatus",
)

message_type_enum = sa.Enum(
    "task_assignment",
    "design_document",
    "code_artifact",
    "code_review",
    "bug_report",
    "status_update",
    "approval",
    "rejection",
    name="messagetype",
)


def upgrade() -> None:
    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("clickup_task_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", task_status_enum, server_default="todo", nullable=False),
        sa.Column("assigned_agent_id", sa.String(100), nullable=True),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tasks_clickup_task_id", "tasks", ["clickup_task_id"])

    # --- agent_messages ---
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("sender_agent_id", sa.String(100), nullable=False),
        sa.Column("recipient_agent_id", sa.String(100), nullable=False),
        sa.Column("message_type", message_type_enum, nullable=False),
        sa.Column("payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_messages_workflow_run_id", "agent_messages", ["workflow_run_id"])
    op.create_index("ix_agent_messages_task_id", "agent_messages", ["task_id"])

    # --- workflow_runs ---
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(50), server_default="running", nullable=False),
        sa.Column("current_node", sa.String(100), server_default="intake", nullable=False),
        sa.Column("state_snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_runs_task_id", "workflow_runs", ["task_id"])

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("input_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("output_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_agent_id", "audit_log", ["agent_id"])
    op.create_index("ix_audit_log_workflow_run_id", "audit_log", ["workflow_run_id"])

    # --- memory_entries ---
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("key", sa.String(500), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_memory_entries_category", "memory_entries", ["category"])
    op.create_index("ix_memory_entries_key", "memory_entries", ["key"])


def downgrade() -> None:
    op.drop_table("memory_entries")
    op.drop_table("audit_log")
    op.drop_table("workflow_runs")
    op.drop_table("agent_messages")
    op.drop_table("tasks")

    # Drop enum types created implicitly
    task_status_enum.drop(op.get_bind(), checkfirst=True)
    message_type_enum.drop(op.get_bind(), checkfirst=True)

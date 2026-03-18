"""Add budget tables, decision ledger, projects, and initiative_id FK on tasks

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

spend_category_enum = sa.Enum(
    "llm_tokens", "compute", "api_calls", "storage", "tooling", "other",
    name="spendcategory",
)
approval_status_enum = sa.Enum(
    "auto_approved", "approved", "denied", "pending", "escalated",
    name="approvalstatus",
)
alert_severity_enum = sa.Enum(
    "info", "warning", "critical",
    name="alertseverity",
)


def upgrade() -> None:
    # --- budget_periods ---
    op.create_table(
        "budget_periods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(50), server_default="global", nullable=False),
        sa.Column("scope_id", sa.String(200), nullable=True),
        sa.Column("total_budget", sa.Float(), server_default="0", nullable=False),
        sa.Column("spent", sa.Float(), server_default="0", nullable=False),
        sa.Column("reserved", sa.Float(), server_default="0", nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD", nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_budget_periods_scope_id", "budget_periods", ["scope_id"])

    # --- spend_records ---
    op.create_table(
        "spend_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("budget_period_id", sa.Uuid(), sa.ForeignKey("budget_periods.id"), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("category", spend_category_enum, server_default="llm_tokens", nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("approval_status", approval_status_enum, server_default="auto_approved", nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_spend_records_budget_period_id", "spend_records", ["budget_period_id"])
    op.create_index("ix_spend_records_workflow_run_id", "spend_records", ["workflow_run_id"])
    op.create_index("ix_spend_records_task_id", "spend_records", ["task_id"])
    op.create_index("ix_spend_records_agent_id", "spend_records", ["agent_id"])

    # --- budget_alerts ---
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("budget_period_id", sa.Uuid(), sa.ForeignKey("budget_periods.id"), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", alert_severity_enum, server_default="warning", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=True),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_budget_alerts_budget_period_id", "budget_alerts", ["budget_period_id"])

    # --- decision_ledger ---
    op.create_table(
        "decision_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("initiative_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), server_default="", nullable=False),
        sa.Column("assumptions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("evidence_refs", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("risks", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("alternatives_considered", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("assumptions_validated", sa.JSON(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_decision_ledger_category", "decision_ledger", ["category"])
    op.create_index("ix_decision_ledger_agent_id", "decision_ledger", ["agent_id"])
    op.create_index("ix_decision_ledger_initiative_id", "decision_ledger", ["initiative_id"])
    op.create_index("ix_decision_ledger_task_id", "decision_ledger", ["task_id"])
    op.create_index("ix_decision_ledger_workflow_run_id", "decision_ledger", ["workflow_run_id"])

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("workspace_path", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("structure", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("key_files", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("conventions", sa.Text(), server_default="", nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Add initiative_id FK to tasks ---
    op.add_column("tasks", sa.Column("initiative_id", sa.Uuid(), nullable=True))
    op.create_index("ix_tasks_initiative_id", "tasks", ["initiative_id"])
    op.create_foreign_key(
        "fk_tasks_initiative_id",
        "tasks",
        "initiatives",
        ["initiative_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_initiative_id", "tasks", type_="foreignkey")
    op.drop_index("ix_tasks_initiative_id", "tasks")
    op.drop_column("tasks", "initiative_id")
    op.drop_table("projects")
    op.drop_table("decision_ledger")
    op.drop_table("budget_alerts")
    op.drop_table("spend_records")
    op.drop_table("budget_periods")
    spend_category_enum.drop(op.get_bind(), checkfirst=True)
    approval_status_enum.drop(op.get_bind(), checkfirst=True)
    alert_severity_enum.drop(op.get_bind(), checkfirst=True)

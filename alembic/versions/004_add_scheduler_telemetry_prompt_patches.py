"""Add scheduler, metric triggers, prompt patches, and telemetry tables

Revision ID: 004
Revises: 003
Create Date: 2026-03-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

patch_status_enum = sa.Enum(
    "proposed", "approved", "rejected", "applied",
    name="patchstatus",
)


def upgrade() -> None:
    # --- scheduled_jobs ---
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("callback_type", sa.String(50), nullable=False),
        sa.Column("callback_args", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_jobs_next_run_at", "scheduled_jobs", ["next_run_at"])
    op.create_index("ix_scheduled_jobs_is_active", "scheduled_jobs", ["is_active"])

    # --- metric_triggers ---
    op.create_table(
        "metric_triggers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("metric_source", sa.String(50), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("comparison", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("action_type", sa.String(50), server_default="portfolio_run", nullable=False),
        sa.Column("action_args", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_value", sa.Float(), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_metric_triggers_is_active", "metric_triggers", ["is_active"])

    # --- prompt_patches ---
    op.create_table(
        "prompt_patches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("prompt_file", sa.String(500), nullable=False),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("action", sa.String(50), server_default="append", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), server_default="", nullable=False),
        sa.Column("expected_improvement", sa.Text(), server_default="", nullable=False),
        sa.Column("status", patch_status_enum, server_default="proposed", nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_patches_agent_id", "prompt_patches", ["agent_id"])
    op.create_index("ix_prompt_patches_status", "prompt_patches", ["status"])

    # --- telemetry_events ---
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("metric_name", sa.String(200), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("dimensions", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("product", sa.String(200), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_telemetry_metric_product_ts", "telemetry_events", ["metric_name", "product", "timestamp"])
    op.create_index("ix_telemetry_source", "telemetry_events", ["source"])


def downgrade() -> None:
    op.drop_table("telemetry_events")
    op.drop_table("prompt_patches")
    op.drop_table("metric_triggers")
    op.drop_table("scheduled_jobs")
    patch_status_enum.drop(op.get_bind(), checkfirst=True)

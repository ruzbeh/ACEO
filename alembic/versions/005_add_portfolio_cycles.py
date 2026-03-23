"""Add portfolio_cycles table for persistent portfolio run state.

Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_cycles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running", index=True),
        sa.Column("current_phase", sa.String(50), nullable=False, server_default="starting"),
        sa.Column("company_goals", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("max_cycles", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("workspace_path", sa.String(1000), nullable=True),
        sa.Column("total_budget", sa.Float(), nullable=False, server_default="0"),
        sa.Column("budget_spent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("budget_remaining", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cycle_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opportunities_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("initiatives_funded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("initiatives_killed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("portfolio_cycles")

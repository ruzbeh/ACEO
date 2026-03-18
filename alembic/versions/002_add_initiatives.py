"""Add initiatives table (top-level unit of work for product company simulator)

Revision ID: 002
Revises: 001
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "initiatives",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), server_default="", nullable=False),
        sa.Column("north_star_metric", sa.String(255), nullable=True),
        sa.Column("local_metric", sa.String(255), nullable=True),
        sa.Column("constraints", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("non_goals", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column("verdict", sa.String(50), server_default="pending", nullable=False),
        sa.Column("evaluation_window_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollout_plan", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("task_graph_snapshot", sa.JSON(), server_default="{}", nullable=False),
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


def downgrade() -> None:
    op.drop_table("initiatives")

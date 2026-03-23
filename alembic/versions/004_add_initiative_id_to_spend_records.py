"""Add initiative_id to spend_records for per-initiative budget tracking.

Revision ID: 004
Revises: 003
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004b"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("spend_records", sa.Column("initiative_id", sa.Uuid(), nullable=True))
    op.create_index("ix_spend_records_initiative_id", "spend_records", ["initiative_id"])


def downgrade() -> None:
    op.drop_index("ix_spend_records_initiative_id", table_name="spend_records")
    op.drop_column("spend_records", "initiative_id")

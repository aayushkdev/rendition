"""add job next run at

Revision ID: c37a8f6df4d2
Revises: b7f0d4e2c9a1
Create Date: 2026-06-06 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c37a8f6df4d2"
down_revision: Union[str, None] = "b7f0d4e2c9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_jobs_status_next_run_at",
        "jobs",
        ["status", "next_run_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_status_next_run_at", table_name="jobs")
    op.drop_column("jobs", "next_run_at")

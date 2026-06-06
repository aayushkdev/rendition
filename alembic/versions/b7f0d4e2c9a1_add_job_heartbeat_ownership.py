"""add job heartbeat ownership

Revision ID: b7f0d4e2c9a1
Revises: 0aecb46bde60
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f0d4e2c9a1"
down_revision: Union[str, None] = "0aecb46bde60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("worker_id", sa.String(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_jobs_running_heartbeat_at",
        "jobs",
        ["heartbeat_at"],
        unique=False,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_running_heartbeat_at", table_name="jobs")
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "worker_id")

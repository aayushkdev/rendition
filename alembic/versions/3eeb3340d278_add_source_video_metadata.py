"""add source video metadata

Revision ID: 3eeb3340d278
Revises: 34d5b4876c76
Create Date: 2026-06-04 01:51:25.767986

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3eeb3340d278"
down_revision: Union[str, Sequence[str], None] = "34d5b4876c76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE processing_status ADD VALUE IF NOT EXISTS 'skipped'")
    op.add_column("videos", sa.Column("source_width", sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("source_height", sa.Integer(), nullable=True))
    op.add_column("videos", sa.Column("source_bitrate", sa.Integer(), nullable=True))
    op.add_column(
        "videos", sa.Column("source_duration_seconds", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("videos", "source_duration_seconds")
    op.drop_column("videos", "source_bitrate")
    op.drop_column("videos", "source_height")
    op.drop_column("videos", "source_width")

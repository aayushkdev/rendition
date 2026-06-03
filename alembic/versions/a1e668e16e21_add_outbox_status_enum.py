"""add outbox status enum

Revision ID: a1e668e16e21
Revises: 1d1c2d5c5dcb
Create Date: 2026-06-02 01:16:28.965528

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1e668e16e21"
down_revision: Union[str, Sequence[str], None] = "1d1c2d5c5dcb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

outbox_status = sa.Enum("pending", "published", name="outbox_status")


def upgrade() -> None:
    """Upgrade schema."""
    outbox_status.create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "outbox_messages",
        "status",
        existing_type=sa.VARCHAR(),
        type_=outbox_status,
        existing_nullable=False,
        postgresql_using="status::outbox_status",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "outbox_messages",
        "status",
        existing_type=outbox_status,
        type_=sa.VARCHAR(),
        existing_nullable=False,
        postgresql_using="status::text",
    )
    outbox_status.drop(op.get_bind(), checkfirst=True)

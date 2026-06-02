"""add partial processing status

Revision ID: 34d5b4876c76
Revises: a1e668e16e21
Create Date: 2026-06-02 16:37:41.346798

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "34d5b4876c76"
down_revision: Union[str, Sequence[str], None] = "a1e668e16e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE processing_status ADD VALUE IF NOT EXISTS 'partial'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL cannot remove enum values without recreating the enum type.
    pass

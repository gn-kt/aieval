"""usage user_id nullable

Revision ID: 578ee9896289
Revises: ee49436aff94
Create Date: 2026-08-01 12:19:48.194644

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '578ee9896289'
down_revision: str | Sequence[str] | None = 'ee49436aff94'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("usage_records", "user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("usage_records", "user_id", existing_type=sa.Integer(), nullable=False)

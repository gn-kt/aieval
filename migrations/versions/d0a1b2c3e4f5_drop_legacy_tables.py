"""drop legacy tables (users, usage_records, sentiment, llm_configs)

Revision ID: d0a1b2c3e4f5
Revises: bef579fc51be
Create Date: 2026-08-09 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd0a1b2c3e4f5'
down_revision: str | Sequence[str] | None = 'bef579fc51be'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop tables removed from models in the v3.2/v3.3 simplification.

    CASCADE 会同时移除 evaluation_records.user_id 指向 users 的外键约束，
    与当前 models.py（user_id 无 ForeignKey）保持一致。
    """
    op.execute("DROP TABLE IF EXISTS sentiment_results CASCADE")
    op.execute("DROP TABLE IF EXISTS sentiment_posts CASCADE")
    op.execute("DROP TABLE IF EXISTS usage_records CASCADE")
    op.execute("DROP TABLE IF EXISTS llm_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")


def downgrade() -> None:
    """这些是已废弃的历史表，不再恢复。"""
    pass

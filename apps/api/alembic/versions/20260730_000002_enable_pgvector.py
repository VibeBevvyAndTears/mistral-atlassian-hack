"""enable pgvector extension

Revision ID: 20260730_000002
Revises: 20260405_000001
Create Date: 2026-07-30 00:00:02
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260730_000002"
down_revision: str | None = "20260405_000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")

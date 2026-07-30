"""add password hash column to users

Revision ID: 20260405_000001
Revises:
Create Date: 2026-04-05 01:00:01
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260405_000001"
down_revision: str | None = "20260730_000001_init"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # password_hash already included in initial migration (20260730_000001_init)
    pass


def downgrade() -> None:
    # No action needed as password_hash was included in initial schema migration
    pass


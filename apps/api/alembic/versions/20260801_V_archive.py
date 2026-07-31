"""Add archived_at to orgs and teams.

Revision ID: 20260801_V_archive
Revises: 20260801_S_dual_approve
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_V_archive"
down_revision: str | None = "20260801_S_dual_approve"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("teams", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "archived_at")
    op.drop_column("orgs", "archived_at")

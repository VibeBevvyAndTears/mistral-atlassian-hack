"""Gap closeout: decision owner_team_id + status.

Revision ID: 20260801_G_gap
Revises: 20260801_M7_eval
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_G_gap"
down_revision: str | None = "20260801_M7_eval"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("owner_team_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_decisions_owner_team_id_teams",
        "decisions",
        "teams",
        ["owner_team_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "decisions",
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
    )
    op.create_index("ix_decisions_status", "decisions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_decisions_status", table_name="decisions")
    op.drop_column("decisions", "status")
    op.drop_constraint("fk_decisions_owner_team_id_teams", "decisions", type_="foreignkey")
    op.drop_column("decisions", "owner_team_id")

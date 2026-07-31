"""PRD closeout C1–C8: package nodes, conflict ack, attached conflicts.

Revision ID: 20260801_R_prd
Revises: 20260801_G_gap
Create Date: 2026-08-01
"""  # noqa: RUF002

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_R_prd"
down_revision: str | None = "20260801_G_gap"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_Json = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "packages",
        sa.Column("included_node_ids", _Json, nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "packages",
        sa.Column(
            "conflicts_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "posts",
        sa.Column(
            "attached_conflicts", _Json, nullable=False, server_default=sa.text("'[]'")
        ),
    )


def downgrade() -> None:
    op.drop_column("posts", "attached_conflicts")
    op.drop_column("packages", "conflicts_acknowledged")
    op.drop_column("packages", "included_node_ids")

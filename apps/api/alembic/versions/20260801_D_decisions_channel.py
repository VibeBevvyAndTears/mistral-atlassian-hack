"""Decision register: channel scope + superseded_by (FR-6.2).

Revision ID: 20260801_D_decisions_channel
Revises: 20260801_U_username
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_D_decisions_channel"
down_revision: str | None = "20260801_U_username"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_decisions_channel_id_channels",
        "decisions",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_decisions_channel_id", "decisions", ["channel_id"])

    op.add_column(
        "decisions",
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_decisions_superseded_by_decisions",
        "decisions",
        "decisions",
        ["superseded_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decisions_superseded_by_decisions", "decisions", type_="foreignkey"
    )
    op.drop_column("decisions", "superseded_by")
    op.drop_index("ix_decisions_channel_id", table_name="decisions")
    op.drop_constraint("fk_decisions_channel_id_channels", "decisions", type_="foreignkey")
    op.drop_column("decisions", "channel_id")

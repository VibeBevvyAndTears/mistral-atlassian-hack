"""Dual-team suggestion approval before applying graph edits.

Revision ID: 20260801_S_dual_approve
Revises: 20260801_D_decisions_channel
Create Date: 2026-08-01

Conceptual:
  B proposes a change → A Lead responds (accept/edit) with proposed_text
  → both teams must approve → only then apply node + regenerate.

Internal:
  - suggestions.proposed_text / applied_at
  - suggestion_approvals (one row per team per suggestion)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_S_dual_approve"
down_revision: str | None = "20260801_D_decisions_channel"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suggestions",
        sa.Column("proposed_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "suggestions",
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "suggestion_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suggestions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "suggestion_id",
            "team_id",
            name="uq_suggestion_approvals_team",
        ),
    )
    op.create_index(
        "ix_suggestion_approvals_suggestion_id",
        "suggestion_approvals",
        ["suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_suggestion_approvals_suggestion_id", table_name="suggestion_approvals")
    op.drop_table("suggestion_approvals")
    op.drop_column("suggestions", "applied_at")
    op.drop_column("suggestions", "proposed_text")

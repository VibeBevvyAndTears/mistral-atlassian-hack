"""M6 polish: team glossary terms.

Revision ID: 20260801_M6_glossary
Revises: 20260801_M5_review
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_M6_glossary"
down_revision: str | None = "20260801_M5_review"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "glossary_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="known"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('known', 'must_explain')",
            name="ck_glossary_terms_kind",
        ),
        sa.UniqueConstraint("team_id", "term", name="uq_glossary_terms_team_term"),
    )
    op.create_index("ix_glossary_terms_org_id", "glossary_terms", ["org_id"])
    op.create_index("ix_glossary_terms_team_id", "glossary_terms", ["team_id"])


def downgrade() -> None:
    op.drop_table("glossary_terms")

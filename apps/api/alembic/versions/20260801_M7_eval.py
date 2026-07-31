"""M7: evaluation goldens and optional judge-verdict overrides.

Revision ID: 20260801_M7_eval
Revises: 20260801_M6_glossary
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_M7_eval"
down_revision: str | None = "20260801_M6_glossary"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    op.create_table(
        "golden_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("input_json", postgresql.JSONB(), nullable=False),
        sa.Column("expected_json", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('conflict', 'judge', 'fidelity')",
            name="ck_golden_examples_kind",
        ),
    )
    op.create_index("ix_golden_examples_org_id", "golden_examples", ["org_id"])
    op.create_index("ix_golden_examples_kind", "golden_examples", ["kind"])

    if "judge_verdicts" in _table_names() and "human_override" not in _column_names(
        "judge_verdicts"
    ):
        op.add_column(
            "judge_verdicts",
            sa.Column("human_override", sa.Boolean(), nullable=True),
        )


def downgrade() -> None:
    if "judge_verdicts" in _table_names() and "human_override" in _column_names(
        "judge_verdicts"
    ):
        op.drop_column("judge_verdicts", "human_override")
    op.drop_table("golden_examples")

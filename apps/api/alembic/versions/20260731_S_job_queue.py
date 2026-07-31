"""Substrate: job_queue table (reconciled S1 — job_queue only).

Revision ID: 20260731_S_job_queue
Revises: 20260730_000002
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260731_S_job_queue"
down_revision: str | None = "20260730_000002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_queue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "completed_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_queue")),
    )
    op.create_index(op.f("ix_job_queue_state"), "job_queue", ["state"], unique=False)
    op.create_index(op.f("ix_job_queue_kind"), "job_queue", ["kind"], unique=False)
    op.create_index(
        op.f("ix_job_queue_dedupe_key"),
        "job_queue",
        ["dedupe_key"],
        unique=False,
    )
    op.create_index(
        "ix_job_queue_claim",
        "job_queue",
        ["state", "next_run_at", "locked_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_queue_claim", table_name="job_queue")
    op.drop_index(op.f("ix_job_queue_dedupe_key"), table_name="job_queue")
    op.drop_index(op.f("ix_job_queue_kind"), table_name="job_queue")
    op.drop_index(op.f("ix_job_queue_state"), table_name="job_queue")
    op.drop_table("job_queue")

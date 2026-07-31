"""M4 delivery tables: channels, packages, posts, renditions, cross_team_access_log.

Revision ID: 20260801_M4_delivery
Revises: 20260801_M3_conflict
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260801_M4_delivery"
down_revision: str | None = "20260801_M3_conflict"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("team_a_id", "team_b_id", name="uq_channels_team_pair"),
        sa.CheckConstraint("team_a_id < team_b_id", name="ck_channels_ordered_pair"),
    )
    op.create_index("ix_channels_org_id", "channels", ["org_id"])

    op.create_table(
        "packages",
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
        sa.Column(
            "target_team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column(
            "bypassed_checks",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "checklist",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
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
    )
    op.create_index("ix_packages_team_id", "packages", ["team_id"])

    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("adapted_body", sa.Text(), nullable=False),
        sa.Column("original_body", sa.Text(), nullable=False),
        sa.Column("what_was_done", sa.Text(), nullable=False, server_default=""),
        sa.Column("ai_priority", sa.String(8), nullable=True),
        sa.Column("ai_priority_reason", sa.Text(), nullable=True),
        sa.Column(
            "topic_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "bypassed_checks",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "updated_since_send",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_posts_channel_id", "posts", ["channel_id"])

    op.create_table(
        "renditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fidelity_verdict", sa.String(16), nullable=True),
        sa.Column("fit_verdict", sa.String(16), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("badge", sa.String(64), nullable=True),
        sa.Column(
            "judge_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_renditions_post_id", "renditions", ["post_id"])

    op.create_table(
        "cross_team_access_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orgs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("who_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("team_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_cross_team_access_log_org_id", "cross_team_access_log", ["org_id"])

    # Realtime: posts (T1-E deferred from M1)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime' LIMIT 1"
            )
        ).fetchone()
        if exists:
            in_pub = bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM pg_publication_tables
                    WHERE pubname = 'supabase_realtime'
                      AND tablename = 'posts' LIMIT 1
                    """
                )
            ).fetchone()
            if not in_pub:
                op.execute(sa.text("ALTER PUBLICATION supabase_realtime ADD TABLE posts"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime' LIMIT 1"
            )
        ).fetchone()
        if exists:
            in_pub = bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM pg_publication_tables
                    WHERE pubname = 'supabase_realtime'
                      AND tablename = 'posts' LIMIT 1
                    """
                )
            ).fetchone()
            if in_pub:
                op.execute(sa.text("ALTER PUBLICATION supabase_realtime DROP TABLE posts"))
    op.drop_table("cross_team_access_log")
    op.drop_table("renditions")
    op.drop_table("posts")
    op.drop_table("packages")
    op.drop_table("channels")

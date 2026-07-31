"""M1-7: Enable Supabase Realtime on notifications + job_queue (T1-E).

posts table does not exist until M4 — deferred. Safe no-op when
supabase_realtime publication is absent (local/CI without Supabase).

Revision ID: 20260801_M1c_realtime
Revises: 20260801_M1b_profile_doc_notif
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260801_M1c_realtime"
down_revision: str | None = "20260801_M1b_profile_doc_notif"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLES = ("notifications", "job_queue")


def _publication_exists(conn) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime' LIMIT 1"
        )
    ).fetchone()
    return row is not None


def _table_in_publication(conn, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'public'
              AND tablename = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _publication_exists(bind):
        # Local/dev without Supabase publication — migration is a documented no-op.
        return
    for table in _TABLES:
        if not _table_in_publication(bind, table):
            op.execute(
                text(f"ALTER PUBLICATION supabase_realtime ADD TABLE {table}")
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _publication_exists(bind):
        return
    for table in _TABLES:
        if _table_in_publication(bind, table):
            op.execute(
                text(f"ALTER PUBLICATION supabase_realtime DROP TABLE {table}")
            )

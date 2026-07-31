"""Substrate: RLS framework helpers (reconciled S2).

Creates set_config helpers for app.current_org_id / app.current_team_id.
Per-table ENABLE ROW LEVEL SECURITY + policies attach in later Mx migrations
when those tables are created.

Revision ID: 20260731_S_rls
Revises: 20260731_S_job_queue
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260731_S_rls"
down_revision: str | None = "20260731_S_job_queue"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Session GUC helpers used by TenantScope (Python) and future RLS policies.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_set_tenant(p_org_id uuid, p_team_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
          PERFORM set_config('app.current_org_id', COALESCE(p_org_id::text, ''), true);
          PERFORM set_config('app.current_team_id', COALESCE(p_team_id::text, ''), true);
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_org_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_org_id', true), '')::uuid;
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_team_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_team_id', true), '')::uuid;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_current_team_id()")
    op.execute("DROP FUNCTION IF EXISTS app_current_org_id()")
    op.execute("DROP FUNCTION IF EXISTS app_set_tenant(uuid, uuid)")

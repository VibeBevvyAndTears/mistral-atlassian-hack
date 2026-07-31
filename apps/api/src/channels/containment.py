"""Cross-team retrieval containment (M4 leak sentinel)."""

from __future__ import annotations

from fastapi import HTTPException, status


def assert_claim_ids_contained(
    *,
    allowed_claim_ids: set[str],
    referenced_claim_ids: set[str],
) -> None:
    """Fail closed if conflict/agent output references claims outside the scan set."""
    leaked = referenced_claim_ids - allowed_claim_ids
    if leaked:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="cross_team_leak_prevented",
        )

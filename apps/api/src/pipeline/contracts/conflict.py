"""Conflict stage JSON contract."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ._common import (
    ClaimRef,
    ConflictClass,
    ConflictScope,
    ConflictSeverity,
    MatchedVia,
)

CONTRACT_VERSION = "1.0.0"


class ConflictInput(BaseModel):
    scope: ConflictScope
    subject_team_id: UUID | str
    counterpart_team_id: UUID | str | None = None
    claims: list[ClaimRef]


class ConflictItem(BaseModel):
    claim_a_id: UUID | str
    claim_b_id: UUID | str
    class_: ConflictClass = Field(alias="class")
    severity: ConflictSeverity
    rationale: str
    matched_via: MatchedVia

    model_config = {
        "populate_by_name": True,
        "ser_json_by_alias": True,
    }


class ConflictOutput(BaseModel):
    """Cross-team: only matched claim ids + rationale — no graph context."""

    conflicts: list[ConflictItem]

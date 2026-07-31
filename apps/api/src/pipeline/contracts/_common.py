"""Shared types for agent stage JSON contracts (design §4.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProposedNode(BaseModel):
    tmp_id: str
    label: str = Field(max_length=64)  # <=5 words enforced in prompts; soft bound here
    type: str
    summary: str
    parent_tmp_id: str | None = None


class ProposedEdge(BaseModel):
    from_tmp_id: str
    to_tmp_id: str
    relation: str


class ClaimType(StrEnum):
    fact = "fact"
    decision = "decision"
    constraint = "constraint"
    requirement = "requirement"
    metric = "metric"
    date = "date"
    owner = "owner"


class ConflictScope(StrEnum):
    intra_team = "intra_team"
    cross_team = "cross_team"


class ConflictClass(StrEnum):
    contradiction = "contradiction"
    update_over_time = "update_over_time"
    scope_diff = "scope_diff"


class ConflictSeverity(StrEnum):
    low = "low"
    med = "med"
    high = "high"


class MatchedVia(StrEnum):
    embedding = "embedding"
    bm25 = "bm25"
    both = "both"


class SubjectType(StrEnum):
    post_body = "post_body"
    comment = "comment"
    suggestion = "suggestion"


class AdaptationDirection(StrEnum):
    forward = "forward"
    reverse = "reverse"


class FidelityVerdict(StrEnum):
    pass_ok = "pass"  # noqa: S105
    fail = "fail"


class FitVerdict(StrEnum):
    pass_ok = "pass"  # noqa: S105
    weak = "weak"
    fail = "fail"


class DetailDepth(StrEnum):
    too_dense = "too_dense"
    ok = "ok"
    too_thin = "too_thin"


class Priority(StrEnum):
    p0 = "p0"
    p1 = "p1"
    p2 = "p2"


class Chunk(BaseModel):
    text: str
    span_start: int
    span_end: int
    heading_path: str | None = None


class ClaimRef(BaseModel):
    claim_id: UUID | str
    text: str | None = None


class ReviewSeed(BaseModel):
    reason: str
    new_node_tmp_id: str | None = None
    existing_node_id: UUID | str | None = None
    confidence: float | None = None


class TeamProfileSnapshot(BaseModel):
    """Version-pinned profile blob for adaptation/judge (opaque for contracts)."""

    team_id: UUID | str
    version: int
    data: dict[str, Any] = Field(default_factory=dict)


class ExtractedClaim(BaseModel):
    node_tmp_id: str
    text: str
    claim_type: ClaimType
    span_start: int
    span_end: int
    confidence: float

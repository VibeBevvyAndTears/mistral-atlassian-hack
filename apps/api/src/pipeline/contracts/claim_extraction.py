"""Claim extraction stage JSON contract."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ._common import Chunk, ExtractedClaim, ProposedNode

CONTRACT_VERSION = "1.0.0"


class ClaimExtractionInput(BaseModel):
    document_id: UUID | str
    team_id: UUID | str
    chunks: list[Chunk] = Field(default_factory=list)
    nodes: list[ProposedNode] = Field(default_factory=list)


class ClaimExtractionOutput(BaseModel):
    claims: list[ExtractedClaim]

"""Linking stage JSON contract."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ._common import ProposedNode, ReviewSeed

CONTRACT_VERSION = "1.0.0"


class LinkingInput(BaseModel):
    team_id: UUID | str
    new_nodes: list[ProposedNode]
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class LinkProposal(BaseModel):
    new_node_tmp_id: str
    existing_node_id: UUID | str | None = None
    relation: str
    confidence: float
    rationale: str


class LinkingOutput(BaseModel):
    links: list[LinkProposal]
    review_items: list[ReviewSeed] = Field(default_factory=list)

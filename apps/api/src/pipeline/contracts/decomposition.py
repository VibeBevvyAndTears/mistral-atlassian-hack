"""Decomposition stage JSON contract."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from ._common import Chunk, ProposedEdge, ProposedNode

CONTRACT_VERSION = "1.0.0"


class DecompositionInput(BaseModel):
    document_id: UUID | str
    team_id: UUID | str
    chunks: list[Chunk]


class DecompositionOutput(BaseModel):
    nodes: list[ProposedNode]
    edges: list[ProposedEdge] = Field(default_factory=list)

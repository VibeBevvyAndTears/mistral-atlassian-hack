"""Graph domain models (M2)."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.lib.database import Base

_Json = JSONB().with_variant(JSON(), "sqlite")
_Uuid = UUID(as_uuid=True)


class AgentTraceRow(Base):
    __tablename__ = "agent_traces"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid_lib.UUID | None] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    job_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    document_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(
        String(128), nullable=False, default="none"
    )
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid_lib.UUID | None] = mapped_column(
        _Uuid, ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_id: Mapped[uuid_lib.UUID | None] = mapped_column(
        _Uuid, ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    span_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    span_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_node_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NodeHistory(Base):
    __tablename__ = "node_history"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    node_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        _Json, nullable=False, default=dict
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="ingest")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimEmbedding(Base):
    __tablename__ = "claim_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "claim_id", "model_version", name="uq_claim_embeddings_claim_model"
        ),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    claim_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[Any]] = mapped_column(_Json, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReviewSeed(Base):
    __tablename__ = "review_seeds"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    new_node_tmp_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    existing_node_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NodeResponse(BaseModel):
    id: str
    team_id: str
    org_id: str
    label: str
    node_type: str
    summary: str
    parent_id: str | None = None
    version: int
    document_id: str | None = None
    created_at: datetime


class NodeHistoryResponse(BaseModel):
    id: str
    node_id: str
    version: int
    snapshot: dict[str, Any] = Field(default_factory=dict)
    source: str
    created_at: datetime


class NodeDiffResponse(BaseModel):
    node_id: str
    from_version: int
    to_version: int
    diff: str

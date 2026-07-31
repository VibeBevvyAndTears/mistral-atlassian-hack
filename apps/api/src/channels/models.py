"""M4 delivery domain models."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
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


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("team_a_id", "team_b_id", name="uq_channels_team_pair"),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_a_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    team_b_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid_lib.UUID | None] = mapped_column(
        _Uuid, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    bypassed_checks: Mapped[list[Any]] = mapped_column(
        _Json, nullable=False, default=list
    )
    checklist: Mapped[dict[str, Any]] = mapped_column(
        _Json, nullable=False, default=dict
    )
    included_node_ids: Mapped[list[Any]] = mapped_column(
        _Json, nullable=False, default=list
    )
    conflicts_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    job_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    created_by: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    adapted_body: Mapped[str] = mapped_column(Text, nullable=False)
    original_body: Mapped[str] = mapped_column(Text, nullable=False)
    what_was_done: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ai_priority_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_tags: Mapped[list[Any]] = mapped_column(_Json, nullable=False, default=list)
    bypassed_checks: Mapped[list[Any]] = mapped_column(
        _Json, nullable=False, default=list
    )
    attached_conflicts: Mapped[list[Any]] = mapped_column(
        _Json, nullable=False, default=list
    )
    updated_since_send: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Rendition(Base):
    __tablename__ = "renditions"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    post_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fidelity_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fit_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    badge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    judge_payload: Mapped[dict[str, Any]] = mapped_column(
        _Json, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CrossTeamAccessLog(Base):
    __tablename__ = "cross_team_access_log"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    who_user_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    team_a_id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, nullable=False)
    team_b_id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    package_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- API schemas ---


class ChannelResponse(BaseModel):
    id: str
    org_id: str
    team_a_id: str
    team_b_id: str
    team_a_name: str | None = None
    team_b_name: str | None = None
    peer_team_id: str | None = None
    peer_team_name: str | None = None
    created_at: datetime


class PackageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=1)
    target_team_id: str
    bypass_incomplete_pipeline: bool = False
    included_node_ids: list[str] = Field(default_factory=list)


class PackageSendBody(BaseModel):
    acknowledge_conflicts: bool = False


class PackageResponse(BaseModel):
    id: str
    team_id: str
    target_team_id: str
    channel_id: str | None
    title: str
    body: str
    status: str
    bypassed_checks: list[str]
    checklist: dict[str, Any]
    included_node_ids: list[str] = Field(default_factory=list)
    conflicts_acknowledged: bool = False
    job_id: str | None = None
    created_at: datetime


class JudgeSummary(BaseModel):
    fidelity: str | None = None
    fit: str | None = None
    overall_confidence: float | None = None
    badge: str | None = None


class PostResponse(BaseModel):
    id: str
    channel_id: str
    package_id: str
    package_title: str | None = None
    version: int
    adapted_body: str
    original_body: str
    what_was_done: str
    ai_priority: str | None = None
    ai_priority_reason: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    bypassed_checks: list[str] = Field(default_factory=list)
    attached_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    updated_since_send: bool = False
    is_read: bool = False
    judge: JudgeSummary | None = None
    sender_team_id: str | None = None
    sender_team_name: str | None = None
    sender_name: str | None = None
    created_at: datetime
    search_score: float | None = None


class ChannelPostsPage(BaseModel):
    """Paginated channel feed (search + page)."""

    items: list[PostResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int
    q: str | None = None


class PostHistoryEntry(BaseModel):
    kind: str  # rendition | suggestion | node | post
    summary: str
    source: str
    created_at: datetime
    node_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PostSourceDocument(BaseModel):
    id: str
    filename: str
    status: str


class PostSourcesResponse(BaseModel):
    package_id: str
    package_title: str
    documents: list[PostSourceDocument] = Field(default_factory=list)

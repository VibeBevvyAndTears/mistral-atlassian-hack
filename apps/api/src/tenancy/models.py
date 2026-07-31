"""Org / membership SQLAlchemy models (M1)."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.lib.database import Base

_Json = JSONB().with_variant(JSON(), "sqlite")
_Uuid = UUID(as_uuid=True)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class OrgMember(Base):
    __tablename__ = "org_members"

    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TeamProfile(Base):
    __tablename__ = "team_profiles"
    __table_args__ = (
        UniqueConstraint("team_id", "version", name="uq_team_profiles_team_version"),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    created_by: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    job_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    uploaded_by: Mapped[uuid_lib.UUID] = mapped_column(
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


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- Pydantic API schemas ---


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: str
    name: str
    created_at: datetime


class MyTeamMembership(BaseModel):
    team_id: str
    team_name: str
    role: str


class MyOrgMembership(BaseModel):
    org_id: str
    org_name: str
    role: str
    teams: list[MyTeamMembership]


class AdminMetricsResponse(BaseModel):
    trace_count: int
    total_cost_usd: float
    average_latency_ms: float | None = None
    job_count: int
    job_pass_rate: float | None = None
    post_count: int
    package_count: int
    suggestion_count: int
    conflict_false_positive_rate: float | None = None
    conflict_resolved_count: int = 0
    conflict_not_a_conflict_count: int = 0


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TeamResponse(BaseModel):
    id: str
    org_id: str
    name: str
    created_at: datetime


class InviteCreate(BaseModel):
    """Invite by email and/or username (at least one required)."""

    email: str | None = Field(default=None, min_length=3, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=32)
    role: str = Field(default="member")


class InviteResponse(BaseModel):
    id: str
    team_id: str
    email: str
    role: str
    token: str
    created_at: datetime
    added_immediately: bool = False


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=8, max_length=128)


class ProfileData(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class ProfileResponse(BaseModel):
    id: str
    team_id: str
    version: int
    data: dict[str, Any]
    created_at: datetime


class ProfileDraftRequest(BaseModel):
    document_ids: list[uuid_lib.UUID] = Field(min_length=1, max_length=3)


class ProfileDraftData(BaseModel):
    purpose: str
    audiences: list[str] = Field(default_factory=list)
    tone: str
    communication_preferences: list[str] = Field(default_factory=list)
    known_terms: list[str] = Field(default_factory=list)


class ProfileDraftResponse(BaseModel):
    document_ids: list[str]
    data: ProfileDraftData
    generated_by: Literal["mistral", "deterministic_stub"]


class ProfileVersionSummary(BaseModel):
    version: int
    created_at: datetime
    created_by: str


class DocumentResponse(BaseModel):
    id: str
    team_id: str
    org_id: str
    filename: str
    status: str
    storage_uri: str | None = None
    job_id: str | None = None
    created_at: datetime

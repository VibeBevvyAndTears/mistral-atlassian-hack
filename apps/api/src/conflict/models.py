"""Conflict / decision domain models (M3)."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.lib.database import Base

_Json = JSONB().with_variant(JSON(), "sqlite")
_Uuid = UUID(as_uuid=True)

Resolution = Literal["keep_a", "keep_b", "keep_both", "not_a_conflict"]


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_a_id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, nullable=False)
    claim_b_id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, nullable=False)
    conflict_class: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    matched_via: Mapped[str] = mapped_column(String(32), nullable=False, default="both")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)  # noqa: E501
    proposed_resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_by: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    resolved_resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_by: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: E501
    payload: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False  # noqa: E501
    )


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("claim_id", name="uq_decisions_claim_id"),)

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="claim_promotion")  # noqa: E501
    owner_team_id: Mapped[uuid_lib.UUID | None] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)  # noqa: E501
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReviewItemResponse(BaseModel):
    id: str
    team_id: str
    claim_a_id: str
    claim_b_id: str
    conflict_class: str
    severity: str
    rationale: str
    matched_via: str
    status: str
    proposed_resolution: str | None = None
    resolved_resolution: str | None = None
    created_at: datetime


class ProposeResolutionRequest(BaseModel):
    resolution: Resolution


class ResolveReviewRequest(BaseModel):
    resolution: Resolution


class DecisionResponse(BaseModel):
    id: str
    team_id: str
    claim_id: str
    title: str
    body: str
    source: str
    status: str = "open"
    owner_team_id: str | None = None
    created_at: datetime

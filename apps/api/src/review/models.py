"""M5 review-loop models."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
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

SuggestionResponseAction = Literal["accept", "edit", "reject"]
SuggestionType = Literal[
    "edit_text",
    "add_detail",
    "flag_incorrect",
    "request_clarification",
    "propose_alternative",
]
ReviewActionType = Literal["agree", "request_changes", "blocked"]


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
    proposer_team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    target_team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id"), nullable=False
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    adapted_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_node_id: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    target_node_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)  # noqa: E501
    response: Mapped[str | None] = mapped_column(String(32), nullable=True)
    response_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by: Mapped[uuid_lib.UUID | None] = mapped_column(_Uuid, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # noqa: E501
    closed_by_receiver: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # noqa: E501
    payload: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False  # noqa: E501
    )


class ReviewAction(Base):
    __tablename__ = "review_actions"
    __table_args__ = (
        UniqueConstraint("post_id", "team_id", "user_id", name="uq_review_actions_actor"),  # noqa: E501
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, ForeignKey("users.id"), nullable=False)  # noqa: E501
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id"), nullable=False
    )
    original_body: Mapped[str] = mapped_column(Text, nullable=False)
    adapted_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReadState(Base):
    __tablename__ = "read_state"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_read_state_user_post"),)  # noqa: E501

    id: Mapped[uuid_lib.UUID] = mapped_column(_Uuid, primary_key=True, default=uuid_lib.uuid4)  # noqa: E501
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SuggestionCreate(BaseModel):
    text: str = Field(min_length=1)
    target_node_id: str | None = None
    suggestion_type: SuggestionType | None = "edit_text"


class SuggestionRespond(BaseModel):
    response: SuggestionResponseAction
    reason: str | None = None
    edited_text: str | None = None


class SuggestionResponse(BaseModel):
    id: str
    post_id: str
    package_id: str
    proposer_team_id: str
    target_team_id: str
    original_text: str
    adapted_preview: str | None = None
    status: str
    response: str | None = None
    response_reason: str | None = None
    target_node_id: str | None = None
    target_node_version: int | None = None
    suggestion_type: SuggestionType | None = None
    created_at: datetime


class ReviewActionCreate(BaseModel):
    action: ReviewActionType
    note: str | None = None


class ReviewActionResponse(BaseModel):
    id: str
    post_id: str
    team_id: str
    action: str
    note: str | None = None
    created_at: datetime


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_team_id: str
    original_body: str
    adapted_body: str | None = None
    created_at: datetime

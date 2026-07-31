"""Evaluation golden-example persistence and API schemas."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.lib.database import Base

_Json = JSONB().with_variant(JSON(), "sqlite")
_Uuid = UUID(as_uuid=True)

GoldenKind = Literal["conflict", "judge", "fidelity"]


class GoldenExample(Base):
    __tablename__ = "golden_examples"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    input_json: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False)
    expected_json: Mapped[dict[str, Any]] = mapped_column(_Json, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GoldenExampleCreate(BaseModel):
    kind: GoldenKind
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    notes: str | None = Field(default=None, max_length=4000)


class GoldenExampleUpdate(BaseModel):
    kind: GoldenKind | None = None
    input_json: dict[str, Any] | None = None
    expected_json: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=4000)


class GoldenExampleResponse(BaseModel):
    id: str
    org_id: str
    kind: GoldenKind
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    notes: str | None
    created_at: datetime


class HumanOverrideRequest(BaseModel):
    human_override: bool


class EvalMetric(BaseModel):
    value: float | None
    threshold: float
    passed: bool
    sample_count: int


class EvalRunResponse(BaseModel):
    status: Literal["passed", "failed", "skipped"]
    warning: str | None = None
    total_goldens: int
    metrics: dict[str, EvalMetric]

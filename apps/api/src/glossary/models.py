"""Team glossary persistence and API schemas."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.lib.database import Base

GlossaryKind = Literal["known", "must_explain"]
_Uuid = UUID(as_uuid=True)


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('known', 'must_explain')",
            name="ck_glossary_terms_kind",
        ),
        UniqueConstraint("team_id", "term", name="uq_glossary_terms_team_term"),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, primary_key=True, default=uuid_lib.uuid4
    )
    org_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid_lib.UUID] = mapped_column(
        _Uuid, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="known")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GlossaryTermCreate(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    definition: str = Field(min_length=1)
    kind: GlossaryKind = "known"


class GlossaryTermUpdate(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=255)
    definition: str | None = Field(default=None, min_length=1)
    kind: GlossaryKind | None = None


class GlossaryTermResponse(BaseModel):
    id: str
    team_id: str
    term: str
    definition: str
    kind: GlossaryKind
    created_at: datetime
    updated_at: datetime

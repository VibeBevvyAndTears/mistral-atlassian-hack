"""Adaptation stage JSON contract."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ._common import AdaptationDirection, SubjectType, TeamProfileSnapshot

CONTRACT_VERSION = "1.0.0"


class AdaptationInput(BaseModel):
    subject_type: SubjectType
    subject_content: str
    source_team_profile: TeamProfileSnapshot
    target_team_profile: TeamProfileSnapshot
    direction: AdaptationDirection


class Substitution(BaseModel):
    original_span: str
    rendered_text: str
    reason: str


class AdaptationOutput(BaseModel):
    body: str
    substitutions: list[Substitution] = Field(default_factory=list)
    what_was_done: str

"""Rendition judge stage JSON contract."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ._common import DetailDepth, FidelityVerdict, FitVerdict, TeamProfileSnapshot

CONTRACT_VERSION = "1.0.0"


class JudgeInput(BaseModel):
    original: str
    rendered: str
    target_profile: TeamProfileSnapshot


class FidelityResult(BaseModel):
    verdict: FidelityVerdict
    invented_facts: list[str] = Field(default_factory=list)
    dropped_facts: list[str] = Field(default_factory=list)
    altered_values: list[str] = Field(default_factory=list)
    rationale: str


class AudienceFitResult(BaseModel):
    verdict: FitVerdict
    jargon_appropriate: bool
    detail_depth_match: DetailDepth
    unexplained_terms: list[str] = Field(default_factory=list)
    rationale: str


class JudgeOutput(BaseModel):
    fidelity: FidelityResult
    audience_fit: AudienceFitResult
    overall_confidence: float = Field(ge=0.0, le=1.0)

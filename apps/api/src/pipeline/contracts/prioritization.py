"""Prioritization stage JSON contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ._common import Priority

CONTRACT_VERSION = "1.0.0"


class PrioritizationInput(BaseModel):
    signals: dict[str, Any] = Field(default_factory=dict)
    content_summary: str | None = None


class PrioritizationOutput(BaseModel):
    priority: Priority
    reason: str
    deterministic_signals: dict[str, Any] = Field(default_factory=dict)

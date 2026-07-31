"""In-memory AgentTrace (DB persistence deferred)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentTrace(BaseModel):
    """Frozen §4.1 trace fields — materialized later into agent_traces."""

    stage: str
    model: str
    prompt_version: str = "none"
    contract_version: str
    input_hash: str
    output: dict[str, Any] | BaseModel
    cost_usd: float | None = None
    latency_ms: float | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))

"""run_agent contract retry tests (no live Mistral)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from src.lib.ai.fakes import FakeAIProvider
from src.pipeline.contracts import (
    CONTRACT_VERSION,
    DecompositionInput,
    DecompositionOutput,
    ProposedNode,
)
from src.pipeline.errors import AgentContractError
from src.pipeline.runner import AgentStage, run_agent


class _BadShape(BaseModel):
    wrong: int


@pytest.mark.asyncio
async def test_run_agent_success() -> None:
    out = DecompositionOutput(
        nodes=[
            ProposedNode(
                tmp_id="n1", label="topic", type="topic", summary="s", parent_tmp_id=None  # noqa: E501
            )
        ],
        edges=[],
    )
    fake = FakeAIProvider(structured_responses=[out])
    inp = DecompositionInput(document_id="d1", team_id="t1", chunks=[])
    result, trace = await run_agent(
        AgentStage.decomposition,
        inp,
        DecompositionOutput,
        provider=fake,
        contract_version=CONTRACT_VERSION,
    )
    assert result.nodes[0].tmp_id == "n1"
    assert trace.stage == "decomposition"
    assert trace.contract_version == CONTRACT_VERSION
    assert trace.prompt_version == "none"
    assert trace.input_hash
    assert trace.latency_ms is not None


@pytest.mark.asyncio
async def test_run_agent_retries_once_on_contract_error() -> None:
    good = DecompositionOutput(
        nodes=[
            ProposedNode(
                tmp_id="n1", label="ok", type="topic", summary="s", parent_tmp_id=None
            )
        ]
    )

    def on_structured(prompt: str, schema: type) -> BaseModel | Exception:
        if "failed contract" in prompt or "Previous output" in prompt:
            return good
        return ValidationError.from_exception_data(
            "DecompositionOutput",
            [{"type": "missing", "loc": ("nodes",), "input": {}, "msg": "Field required"}],  # noqa: E501
        )

    fake = FakeAIProvider(on_structured=on_structured)
    inp = DecompositionInput(document_id="d1", team_id="t1", chunks=[])
    result, trace = await run_agent(
        AgentStage.decomposition,
        inp,
        DecompositionOutput,
        provider=fake,
    )
    assert result.nodes[0].tmp_id == "n1"
    assert len(fake.structured_calls) == 2
    assert trace.stage == "decomposition"


@pytest.mark.asyncio
async def test_run_agent_fails_after_retry() -> None:
    def always_bad(prompt: str, schema: type) -> Exception:
        del prompt, schema
        return ValidationError.from_exception_data(
            "DecompositionOutput",
            [{"type": "missing", "loc": ("nodes",), "input": {}, "msg": "Field required"}],  # noqa: E501
        )

    fake = FakeAIProvider(on_structured=always_bad)
    inp = DecompositionInput(document_id="d1", team_id="t1", chunks=[])
    with pytest.raises(AgentContractError):
        await run_agent(
            AgentStage.decomposition,
            inp,
            DecompositionOutput,
            provider=fake,
        )
    assert len(fake.structured_calls) == 2

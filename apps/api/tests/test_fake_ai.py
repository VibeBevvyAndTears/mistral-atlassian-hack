"""FakeAIProvider unit tests."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.lib.ai.fakes import FakeAIProvider


class _Out(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_fake_ai_generate_structured() -> None:
    fake = FakeAIProvider(structured_responses=[_Out(value="hello")])
    result = await fake.generate_structured("prompt", _Out)
    assert result.value == "hello"
    assert len(fake.structured_calls) == 1


@pytest.mark.asyncio
async def test_fake_ai_generate_text() -> None:
    fake = FakeAIProvider(text_response="pong")
    assert await fake.generate_text("ping") == "pong"

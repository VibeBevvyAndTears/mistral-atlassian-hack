"""Test doubles for AIProvider."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.lib.ai.base import AIProvider

T = TypeVar("T")


class FakeAIProvider(AIProvider[T]):
    """In-memory AIProvider for unit tests — no live Mistral calls."""

    def __init__(
        self,
        *,
        structured_responses: list[BaseModel | Exception] | None = None,
        text_response: str = "ok",
        on_structured: Callable[[str, type[Any]], BaseModel | Exception] | None = None,
    ) -> None:
        self.structured_responses = list(structured_responses or [])
        self.text_response = text_response
        self.on_structured = on_structured
        self.structured_calls: list[tuple[str, type[Any]]] = []
        self.text_calls: list[str] = []

    async def analyze_image(self, image_data: bytes | list[bytes]) -> T:
        del image_data
        raise NotImplementedError

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        del kwargs
        self.text_calls.append(prompt)
        return self.text_response

    async def generate_stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        del kwargs
        yield await self.generate_text(prompt)

    async def generate_structured(
        self, prompt: str, schema: type[T], **kwargs: Any
    ) -> T:
        del kwargs
        self.structured_calls.append((prompt, schema))
        if self.on_structured is not None:
            result = self.on_structured(prompt, schema)
        elif self.structured_responses:
            result = self.structured_responses.pop(0)
        else:
            raise RuntimeError("FakeAIProvider has no structured response queued")

        if isinstance(result, Exception):
            raise result
        if not isinstance(result, schema):
            # Allow dict-like BaseModel rebuild / ValidationError path
            if isinstance(result, BaseModel):
                try:
                    return schema.model_validate(result.model_dump())  # type: ignore[return-value]
                except ValidationError:
                    raise
            raise TypeError(f"expected {schema.__name__}, got {type(result)}")
        return result  # type: ignore[return-value]

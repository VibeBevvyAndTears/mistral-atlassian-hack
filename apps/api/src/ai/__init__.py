"""AI provider factory — production path is Mistral only."""

from __future__ import annotations

from functools import lru_cache

from src.ai.mistral import MistralProvider
from src.lib.ai.base import AIProvider
from src.lib.config import settings


@lru_cache
def get_mistral_provider() -> MistralProvider:
    """Return the shared MistralProvider (chat + embed).

    Raises ValueError if ``MISTRAL_API_KEY`` is missing or kill switch is on.
    """
    if settings.MISTRAL_KILL_SWITCH:
        raise RuntimeError("MISTRAL_KILL_SWITCH is enabled — LLM calls blocked")
    key = settings.MISTRAL_API_KEY
    if not key:
        raise ValueError("MISTRAL_API_KEY is required for MistralProvider")
    return MistralProvider(
        api_key=key,
        chat_model=settings.MISTRAL_CHAT_MODEL,
        embed_model=settings.MISTRAL_EMBED_MODEL,
        ocr_model=settings.MISTRAL_OCR_MODEL,
    )


def get_ai_provider() -> AIProvider:
    """Production AIProvider. Always Mistral for this product."""
    return get_mistral_provider()

"""Mistral Studio AIProvider implementation (S3 / design §5.4)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from mistralai import Mistral
from mistralai.models import JSONSchema, ResponseFormat, UserMessage
from pydantic import BaseModel

from src.lib.ai.base import AIProvider
from src.lib.ai.telemetry import GenAIOperation, genai_span, provider_name

T = TypeVar("T")

DEFAULT_CHAT_MODEL = "mistral-large-latest"
DEFAULT_EMBED_MODEL = "mistral-embed"
DEFAULT_OCR_MODEL = "mistral-ocr-latest"


class MistralProvider(AIProvider[T]):
    """Only module that talks to Mistral for structured/chat/embed calls."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        chat_model: str = DEFAULT_CHAT_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        ocr_model: str = DEFAULT_OCR_MODEL,
        client: Mistral | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._embed_model = embed_model
        self._ocr_model = ocr_model
        if client is not None:
            self._client = client
        else:
            key = api_key if api_key is not None else os.environ.get("MISTRAL_API_KEY", "")  # noqa: E501
            if not key:
                raise ValueError("MISTRAL_API_KEY is required for MistralProvider")
            self._client = Mistral(api_key=key)

    async def analyze_image(self, image_data: bytes | list[bytes]) -> T:
        del image_data
        raise NotImplementedError("MistralProvider.analyze_image is not used in v1")

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        model = kwargs.get("model", self._chat_model)
        with genai_span(
            operation=GenAIOperation.CHAT,
            provider=provider_name("mistral"),
            request_model=model,
        ) as call:
            response = await self._client.chat.complete_async(
                model=model,
                messages=[UserMessage(content=prompt)],
            )
            content = ""
            if response is not None and response.choices:
                raw = response.choices[0].message.content
                content = raw if isinstance(raw, str) else ""
            usage = getattr(response, "usage", None)
            call.set_response(
                model=getattr(response, "model", model),
                response_id=getattr(response, "id", None),
                finish_reasons=[
                    getattr(c, "finish_reason", None) for c in (response.choices or [])
                ]
                if response
                else None,
                input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                output_tokens=getattr(usage, "completion_tokens", None) if usage else None,  # noqa: E501
            )
            return content

    async def generate_stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        model = kwargs.get("model", self._chat_model)
        stream = await self._client.chat.stream_async(
            model=model,
            messages=[UserMessage(content=prompt)],
        )
        async for event in stream:
            delta = getattr(getattr(event, "data", None), "choices", None)
            if not delta:
                continue
            content = getattr(delta[0].delta, "content", None)
            if isinstance(content, str) and content:
                yield content

    async def generate_structured(
        self, prompt: str, schema: type[T], **kwargs: Any
    ) -> T:
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError("schema must be a Pydantic BaseModel subclass")

        model = kwargs.get("model", self._chat_model)
        json_schema = schema.model_json_schema()
        response_format = ResponseFormat(
            type="json_schema",
            json_schema=JSONSchema(
                name=schema.__name__,
                schema_definition=json_schema,
                strict=True,
            ),
        )

        with genai_span(
            operation=GenAIOperation.CHAT,
            provider=provider_name("mistral"),
            request_model=model,
        ) as call:
            response = await self._client.chat.complete_async(
                model=model,
                messages=[UserMessage(content=prompt)],
                response_format=response_format,
            )
            content = ""
            if response is not None and response.choices:
                raw = response.choices[0].message.content
                content = raw if isinstance(raw, str) else json.dumps(raw)
            usage = getattr(response, "usage", None)
            call.set_response(
                model=getattr(response, "model", model),
                response_id=getattr(response, "id", None),
                finish_reasons=[
                    getattr(c, "finish_reason", None) for c in (response.choices or [])
                ]
                if response
                else None,
                input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                output_tokens=getattr(usage, "completion_tokens", None) if usage else None,  # noqa: E501
            )
            return schema.model_validate_json(content)  # type: ignore[return-value]

    async def embed(self, text: str) -> list[float]:
        """Embedding helper for retrieval (mistral-embed)."""
        with genai_span(
            operation=GenAIOperation.EMBEDDINGS,
            provider=provider_name("mistral"),
            request_model=self._embed_model,
        ) as call:
            resp = await self._client.embeddings.create_async(
                model=self._embed_model, inputs=[text]
            )
            embedding = resp.data[0].embedding if resp.data else None
            call.set_response(model=self._embed_model)
            return list(embedding) if embedding is not None else []

    async def ocr_document(self, data: bytes, *, filename: str = "document.pdf") -> str:
        """Run Mistral OCR on a PDF or image (FR-3.1 scanned documents)."""
        import base64

        if not data:
            raise ValueError("OCR input is empty")
        lower = filename.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }[next(ext for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif") if lower.endswith(ext))]  # noqa: E501
            data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
            document: dict[str, str] = {"type": "image_url", "image_url": data_url}
        else:
            data_url = (
                f"data:application/pdf;base64,{base64.b64encode(data).decode('ascii')}"
            )
            document = {
                "type": "document_url",
                "document_url": data_url,
                "document_name": filename,
            }

        model = self._ocr_model
        with genai_span(
            operation=GenAIOperation.CHAT,
            provider=provider_name("mistral"),
            request_model=model,
        ) as call:
            response = await self._client.ocr.process_async(
                model=model,
                document=document,
            )
            pages = getattr(response, "pages", None) or []
            parts: list[str] = []
            for page in pages:
                md = getattr(page, "markdown", None)
                if isinstance(md, str) and md.strip():
                    parts.append(md.strip())
            text = "\n\n".join(parts).strip()
            usage = getattr(response, "usage_info", None) or getattr(response, "usage", None)  # noqa: E501
            call.set_response(
                model=model,
                input_tokens=getattr(usage, "pages_processed", None) if usage else None,
            )
            if not text:
                raise ValueError("Mistral OCR returned empty text")
            return text

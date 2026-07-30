import os

from fastapi import APIRouter
from mistralai import Mistral
from mistralai.models import AssistantMessage, SystemMessage, ToolMessage, UserMessage
from pydantic import BaseModel

router = APIRouter()


def get_mistral_client() -> Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    return Mistral(api_key=api_key)


class ChatRequest(BaseModel):
    prompt: str


class EmbedRequest(BaseModel):
    text: str


async def call_agent(prompt: str) -> str:
    client = get_mistral_client()
    messages: list[AssistantMessage | SystemMessage | ToolMessage | UserMessage] = [
        UserMessage(content=prompt)
    ]
    response = await client.chat.complete_async(
        model="mistral-large-latest",
        messages=messages,
    )
    if response is None or not response.choices:
        return ""
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content
    return ""


async def embed_text(text: str) -> list[float]:
    client = get_mistral_client()
    resp = await client.embeddings.create_async(model="mistral-embed", inputs=[text])
    embedding = resp.data[0].embedding
    return embedding if embedding is not None else []


@router.post("/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, str]:
    content = await call_agent(req.prompt)
    return {"response": content}


@router.post("/embed")
async def embed_endpoint(req: EmbedRequest) -> dict[str, list[float]]:
    embedding = await embed_text(req.text)
    return {"embedding": embedding}

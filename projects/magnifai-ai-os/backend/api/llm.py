"""LLM API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    client_id: str | None = None


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat completion request (mock for now)."""
    return ChatResponse(
        content="Mock response",
        model=request.model or "gpt-4o",
        provider=request.provider or "openai",
        input_tokens=10,
        output_tokens=20,
        latency_ms=100.0,
    )


@router.get("/providers")
async def list_providers():
    """List available LLM providers."""
    return {
        "providers": [
            {"name": "openai", "available": True},
            {"name": "claude", "available": True},
            {"name": "gemini", "available": True},
        ]
    }


@router.get("/health")
async def llm_health():
    """Check LLM subsystem health."""
    return {"status": "ok", "providers": ["openai", "claude", "gemini"]}

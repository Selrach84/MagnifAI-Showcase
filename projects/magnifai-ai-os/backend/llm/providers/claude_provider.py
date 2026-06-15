import time

from anthropic import AsyncAnthropic
from anthropic.types import TextBlock

from backend.llm.providers.base import BaseProvider, EmbeddingResponse, LLMResponse


class ClaudeProvider(BaseProvider):
    provider_name = "claude"

    def __init__(self, api_key: str, default_model: str = "claude-3-5-sonnet-20241022") -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.client = AsyncAnthropic(api_key=api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self.default_model
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append(msg)

        start = time.perf_counter()

        if system_message:
            response = await self.client.messages.create(
                model=model,
                messages=chat_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                system=system_message,
            )
        else:
            response = await self.client.messages.create(
                model=model,
                messages=chat_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        latency_ms = (time.perf_counter() - start) * 1000

        # Extract text from the first TextBlock content block
        content_block = response.content[0]
        if isinstance(content_block, TextBlock):
            text = content_block.text
        else:
            # For other block types, we cannot extract text; raise an error or use str()
            text = str(content_block)

        return LLMResponse(
            content=text,
            model=response.model,
            provider=self.provider_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason or "end_turn",
            latency_ms=round(latency_ms, 2),
        )

    async def embed(self, text: str, model: str | None = None) -> EmbeddingResponse:
        raise NotImplementedError("Claude does not support embeddings")

    async def health_check(self) -> bool:
        try:
            await self.client.messages.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

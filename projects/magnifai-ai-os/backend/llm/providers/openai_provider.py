import time

from openai import AsyncOpenAI

from backend.llm.providers.base import BaseProvider, EmbeddingResponse, LLMResponse


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, default_model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self.default_model
        start = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.provider_name,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            finish_reason=choice.finish_reason or "stop",
            latency_ms=round(latency_ms, 2),
        )

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> EmbeddingResponse:
        response = await self.client.embeddings.create(model=model, input=text)
        return EmbeddingResponse(
            embedding=response.data[0].embedding,
            model=response.model,
            provider=self.provider_name,
            tokens=response.usage.prompt_tokens,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

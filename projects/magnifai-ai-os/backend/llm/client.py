from backend.llm.config import LLMConfig
from backend.llm.providers.base import BaseProvider, EmbeddingResponse, LLMResponse
from backend.llm.providers.claude_provider import ClaudeProvider
from backend.llm.providers.gemini_provider import GeminiProvider
from backend.llm.providers.openai_provider import OpenAIProvider
from backend.llm.tracker import UsageTracker


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._providers: dict[str, BaseProvider] = {}
        self.tracker = UsageTracker()

        for name in ("openai", "claude", "gemini"):
            provider_cfg = getattr(config, name, None)
            if provider_cfg is not None:
                self._providers[name] = self._create_provider(
                    name, provider_cfg.api_key, provider_cfg.default_model
                )

    @staticmethod
    def _create_provider(name: str, api_key: str, default_model: str) -> BaseProvider:
        providers = {
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "gemini": GeminiProvider,
        }
        return providers[name](api_key=api_key, default_model=default_model)

    def _resolve_provider(self, provider: str | None, model: str | None) -> str:
        if provider and provider in self._providers:
            return provider
        for name in self._config.auto_provider_preference:
            if name in self._providers:
                return name
        raise ValueError("No providers available")

    async def chat(
        self,
        messages: list[dict],
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        client_id: str = "",
        automation_id: str = "",
    ) -> LLMResponse:
        resolved = self._resolve_provider(provider, model)
        preference = self._config.auto_provider_preference
        ordered = [resolved] + [p for p in preference if p != resolved and p in self._providers]

        last_error: Exception | None = None
        for name in ordered:
            try:
                prov = self._providers[name]
                response = await prov.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if client_id:
                    self.tracker.record(
                        client_id=client_id,
                        automation_id=automation_id,
                        provider=response.provider,
                        model=response.model,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        latency_ms=response.latency_ms,
                    )
                return response
            except Exception as exc:
                last_error = exc
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")

    async def embed(
        self,
        text: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> EmbeddingResponse:
        resolved = self._resolve_provider(provider, model)
        return await self._providers[resolved].embed(text=text, model=model)

    async def health_check(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, prov in self._providers.items():
            try:
                results[name] = await prov.health_check()
            except Exception:
                results[name] = False
        return results

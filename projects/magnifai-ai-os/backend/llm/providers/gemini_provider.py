import time

import google.generativeai as genai

from backend.llm.providers.base import BaseProvider, EmbeddingResponse, LLMResponse

# Map Gemini finish_reason integers to human-readable strings
_FINISH_REASON_MAP = {
    0: "stop",
    1: "stop",
    2: "safety",
    3: "recitation",
    4: "other",
}


class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def __init__(self, api_key: str, default_model: str = "gemini-1.5-pro") -> None:
        self.api_key = api_key
        self.default_model = default_model
        genai.configure(api_key=api_key)

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self.default_model

        system_instruction = None
        contents = []

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})

        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        start = time.perf_counter()
        response = await gen_model.generate_content_async(contents)
        latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage_metadata
        finish = (
            _FINISH_REASON_MAP.get(response.candidates[0].finish_reason, "unknown")
            if response.candidates
            else "unknown"
        )

        return LLMResponse(
            content=response.text or "",
            model=model,
            provider=self.provider_name,
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            total_tokens=usage.total_token_count,
            finish_reason=finish,
            latency_ms=round(latency_ms, 2),
        )

    async def embed(self, text: str, model: str = "text-embedding-004") -> EmbeddingResponse:
        result = await genai.embed_content_async(model=model, content=text)
        return EmbeddingResponse(
            embedding=result.embedding.values,
            model=model,
            provider=self.provider_name,
            tokens=result.total_token_count,
        )

    async def health_check(self) -> bool:
        try:
            model = genai.GenerativeModel(self.default_model)
            await model.generate_content_async("ping")
            return True
        except Exception:
            return False

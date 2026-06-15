from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str
    latency_ms: float


@dataclass
class EmbeddingResponse:
    embedding: list[float]
    model: str
    provider: str
    tokens: int


class BaseProvider(ABC):
    provider_name: str

    @abstractmethod
    async def chat(self, messages, model=None, temperature=0.7, max_tokens=4096) -> LLMResponse: ...

    @abstractmethod
    async def embed(self, text, model=None) -> EmbeddingResponse: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

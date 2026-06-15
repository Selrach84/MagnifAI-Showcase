from abc import ABC, abstractmethod

from pydantic import BaseModel


class AgentConfig(BaseModel):
    id: str
    name: str
    type: str  # "llm", "automation", "hybrid"
    provider: str | None = None
    model: str | None = None
    system_prompt: str = ""
    max_iterations: int = 10


class AgentResponse(BaseModel):
    agent_id: str
    status: str  # "success", "error", "timeout"
    output: dict = {}
    error: str = ""
    iterations: int = 0
    latency_ms: float = 0.0


class BaseAgent(ABC):
    agent_type: str

    @abstractmethod
    async def execute(self, task: dict, config: AgentConfig) -> AgentResponse:
        ...

    @abstractmethod
    async def validate_task(self, task: dict) -> tuple[bool, list[str]]:
        ...

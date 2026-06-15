import time

from backend.agents.base import AgentConfig, AgentResponse, BaseAgent
from backend.llm.client import LLMClient


class LLMAgent(BaseAgent):
    agent_type = "llm"

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def validate_task(self, task: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if "messages" not in task and "prompt" not in task:
            errors.append("Task must contain 'messages' or 'prompt'")
        return len(errors) == 0, errors

    async def execute(self, task: dict, config: AgentConfig) -> AgentResponse:
        start = time.monotonic()
        valid, errors = await self.validate_task(task)
        if not valid:
            return AgentResponse(
                agent_id=config.id,
                status="error",
                error="; ".join(errors),
            )

        messages = task.get("messages", [])
        if not messages and "prompt" in task:
            messages = [{"role": "user", "content": task["prompt"]}]

        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        iterations = 0
        last_content = ""
        for i in range(config.max_iterations):
            iterations = i + 1
            try:
                response = await self.llm_client.chat(
                    messages=messages,
                    provider=config.provider,
                    model=config.model,
                )
                last_content = response.content

                if task.get("auto_continue") and i < config.max_iterations - 1:
                    messages.append({"role": "assistant", "content": last_content})
                    messages.append({"role": "user", "content": "Continue."})
                else:
                    break
            except Exception as exc:
                return AgentResponse(
                    agent_id=config.id,
                    status="error",
                    error=str(exc),
                    iterations=iterations,
                    latency_ms=(time.monotonic() - start) * 1000,
                )

        return AgentResponse(
            agent_id=config.id,
            status="success",
            output={"content": last_content},
            iterations=iterations,
            latency_ms=(time.monotonic() - start) * 1000,
        )

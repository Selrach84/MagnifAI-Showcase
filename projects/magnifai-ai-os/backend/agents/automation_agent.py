import asyncio
import time

from backend.agents.base import AgentConfig, AgentResponse, BaseAgent
from backend.templates.engine import TemplateEngine


class AutomationAgent(BaseAgent):
    agent_type = "automation"

    def __init__(self, template_engine: TemplateEngine) -> None:
        self.template_engine = template_engine

    async def validate_task(self, task: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if "template_id" not in task:
            errors.append("Task must contain 'template_id'")
        if "config" not in task:
            errors.append("Task must contain 'config'")
        return len(errors) == 0, errors

    async def _execute_step(self, step: dict) -> dict:
        step_type = step.get("type", "webhook")
        if step_type == "delay":
            await asyncio.sleep(step.get("duration", 0))
            return {"step": step.get("name", "delay"), "status": "completed", "output": {}}
        if step_type == "webhook":
            return {
                "step": step.get("name", "webhook"),
                "status": "completed",
                "output": {"url": step.get("url", ""), "method": step.get("method", "POST")},
            }
        if step_type == "llm":
            return {
                "step": step.get("name", "llm"),
                "status": "completed",
                "output": {"prompt": step.get("prompt", "")},
            }
        if step_type == "conditional":
            return {
                "step": step.get("name", "conditional"),
                "status": "completed",
                "output": {"condition": step.get("condition", "")},
            }
        return {"step": step.get("name", "unknown"), "status": "skipped", "output": {}}

    async def execute(self, task: dict, config: AgentConfig) -> AgentResponse:
        start = time.monotonic()
        valid, errors = await self.validate_task(task)
        if not valid:
            return AgentResponse(
                agent_id=config.id,
                status="error",
                error="; ".join(errors),
            )

        try:
            workflow = self.template_engine.render_workflow(
                task["template_id"], task["config"]
            )
        except (KeyError, ValueError) as exc:
            return AgentResponse(
                agent_id=config.id,
                status="error",
                error=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )

        step_results = []
        for step in workflow.get("steps", []):
            result = await self._execute_step(step)
            step_results.append(result)

        return AgentResponse(
            agent_id=config.id,
            status="success",
            output={"workflow": workflow.get("template_id"), "steps": step_results},
            iterations=len(step_results),
            latency_ms=(time.monotonic() - start) * 1000,
        )

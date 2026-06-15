"""Agent management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.base import AgentConfig
from backend.agents.orchestrator import AgentOrchestrator

router = APIRouter(prefix="/api/agents", tags=["agents"])

orchestrator = AgentOrchestrator()


class RegisterAgentRequest(BaseModel):
    id: str
    name: str
    type: str
    provider: str | None = None
    model: str | None = None
    system_prompt: str = ""
    max_iterations: int = 10


class ExecuteTaskRequest(BaseModel):
    task: dict


@router.post("")
async def register_agent(request: RegisterAgentRequest):
    config = AgentConfig(**request.model_dump())
    from backend.agents.llm_agent import LLMAgent
    from backend.llm.client import LLMClient
    from backend.llm.config import LLMConfig

    if config.type == "llm":
        agent = LLMAgent(llm_client=LLMClient(config=LLMConfig()))
    else:
        from backend.agents.automation_agent import AutomationAgent
        from backend.templates.engine import TemplateEngine

        agent = AutomationAgent(template_engine=TemplateEngine())
    orchestrator.register_agent(agent, config)
    return {"id": config.id, "name": config.name, "type": config.type}


@router.get("")
async def list_agents():
    return {"agents": orchestrator.list_agents()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    agent = orchestrator.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    agents = orchestrator.list_agents()
    for a in agents:
        if a["id"] == agent_id:
            return a
    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")


@router.post("/{agent_id}/execute")
async def execute_agent(agent_id: str, request: ExecuteTaskRequest):
    response = await orchestrator.execute_agent(agent_id, request.task)
    return response.model_dump()


@router.get("/{agent_id}/history")
async def get_agent_history(agent_id: str):
    agent = orchestrator.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    history = orchestrator.get_execution_history(agent_id)
    return {"history": [h.model_dump() for h in history]}

import pytest

from backend.agents.base import AgentConfig, AgentResponse, BaseAgent
from backend.agents.llm_agent import LLMAgent
from backend.agents.orchestrator import AgentOrchestrator


class DummyAgent(BaseAgent):
    agent_type = "dummy"

    async def validate_task(self, task: dict) -> tuple[bool, list[str]]:
        if "input" in task:
            return True, []
        return False, ["Missing 'input'"]

    async def execute(self, task: dict, config: AgentConfig) -> AgentResponse:
        valid, errors = await self.validate_task(task)
        if not valid:
            return AgentResponse(agent_id=config.id, status="error", error="; ".join(errors))
        return AgentResponse(
            agent_id=config.id,
            status="success",
            output={"result": task["input"]},
        )


def test_base_agent_interface():
    with pytest.raises(TypeError):
        BaseAgent()


@pytest.mark.asyncio
async def test_dummy_agent_execute():
    agent = DummyAgent()
    config = AgentConfig(id="d1", name="Dummy", type="dummy")
    response = await agent.execute({"input": "hello"}, config)
    assert response.status == "success"
    assert response.output == {"result": "hello"}


@pytest.mark.asyncio
async def test_dummy_agent_validation_fails():
    agent = DummyAgent()
    config = AgentConfig(id="d1", name="Dummy", type="dummy")
    response = await agent.execute({}, config)
    assert response.status == "error"
    assert "Missing" in response.error


def test_orchestrator_register():
    orch = AgentOrchestrator()
    agent = DummyAgent()
    config = AgentConfig(id="d1", name="Dummy", type="dummy")
    orch.register_agent(agent, config)
    assert orch.get_agent("d1") is agent
    assert len(orch.list_agents()) == 1


@pytest.mark.asyncio
async def test_orchestrator_execute():
    orch = AgentOrchestrator()
    agent = DummyAgent()
    config = AgentConfig(id="d1", name="Dummy", type="dummy")
    orch.register_agent(agent, config)
    response = await orch.execute_agent("d1", {"input": "test"})
    assert response.status == "success"
    assert response.output == {"result": "test"}
    assert len(orch.get_execution_history("d1")) == 1


@pytest.mark.asyncio
async def test_orchestrator_execute_unknown_agent():
    orch = AgentOrchestrator()
    response = await orch.execute_agent("nonexistent", {"input": "test"})
    assert response.status == "error"
    assert "not found" in response.error


def test_agent_config_validation():
    with pytest.raises((TypeError, ValueError)):
        AgentConfig(id=123, name="Bad", type="llm")  # type: ignore


@pytest.mark.asyncio
async def test_llm_agent_execute():
    class MockLLMClient:
        async def chat(self, **kwargs):
            class R:
                content = "mock response"
                provider = "openai"
                model = "gpt-4o"
                input_tokens = 10
                output_tokens = 20
                latency_ms = 50.0
            return R()

    agent = LLMAgent(llm_client=MockLLMClient())
    config = AgentConfig(id="l1", name="LLM", type="llm")
    response = await agent.execute({"prompt": "hello"}, config)
    assert response.status == "success"
    assert response.output["content"] == "mock response"


@pytest.mark.asyncio
async def test_llm_agent_validation_fails():
    class MockLLMClient:
        pass

    agent = LLMAgent(llm_client=MockLLMClient())
    config = AgentConfig(id="l1", name="LLM", type="llm")
    response = await agent.execute({}, config)
    assert response.status == "error"

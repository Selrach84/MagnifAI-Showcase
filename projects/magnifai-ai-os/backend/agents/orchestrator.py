from backend.agents.base import AgentConfig, AgentResponse, BaseAgent


class AgentOrchestrator:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._configs: dict[str, AgentConfig] = {}
        self._history: dict[str, list[AgentResponse]] = {}

    def register_agent(self, agent: BaseAgent, config: AgentConfig) -> None:
        self._agents[config.id] = agent
        self._configs[config.id] = config
        self._history[config.id] = []

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[dict]:
        return [
            {
                "id": cfg.id,
                "name": cfg.name,
                "type": cfg.type,
                "provider": cfg.provider,
                "model": cfg.model,
            }
            for cfg in self._configs.values()
        ]

    def get_execution_history(self, agent_id: str) -> list[AgentResponse]:
        return self._history.get(agent_id, [])

    async def execute_agent(self, agent_id: str, task: dict) -> AgentResponse:
        agent = self._agents.get(agent_id)
        if agent is None:
            return AgentResponse(
                agent_id=agent_id,
                status="error",
                error=f"Agent not found: {agent_id}",
            )
        config = self._configs[agent_id]
        response = await agent.execute(task, config)
        self._history[agent_id].append(response)
        return response

import uuid
from datetime import UTC, datetime

from backend.agents.base import AgentResponse


class ExecutionLogger:
    def __init__(self) -> None:
        self._logs: list[dict] = []

    def log_execution(
        self,
        agent_id: str,
        task: dict,
        response: AgentResponse,
        duration_ms: float,
    ) -> dict:
        entry = {
            "id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "task": task,
            "status": response.status,
            "output": response.output,
            "error": response.error,
            "iterations": response.iterations,
            "latency_ms": response.latency_ms,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._logs.append(entry)
        return entry

    def get_execution_history(self, agent_id: str, limit: int = 100) -> list[dict]:
        agent_logs = [log for log in self._logs if log["agent_id"] == agent_id]
        return agent_logs[-limit:]

    def get_execution_stats(self, agent_id: str) -> dict:
        agent_logs = [log for log in self._logs if log["agent_id"] == agent_id]
        if not agent_logs:
            return {"total": 0, "success": 0, "error": 0, "avg_latency_ms": 0.0}
        success = sum(1 for log in agent_logs if log["status"] == "success")
        error = sum(1 for log in agent_logs if log["status"] == "error")
        avg_latency = sum(log["latency_ms"] for log in agent_logs) / len(agent_logs)
        return {
            "total": len(agent_logs),
            "success": success,
            "error": error,
            "avg_latency_ms": round(avg_latency, 2),
        }

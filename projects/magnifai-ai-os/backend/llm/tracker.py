from dataclasses import dataclass, field
from datetime import UTC, datetime

COST_PER_1M_TOKENS: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "text-embedding-3-small": (0.02, 0.0),
        "text-embedding-3-large": (0.13, 0.0),
    },
    "claude": {
        "claude-3-5-sonnet-20241022": (3.00, 15.00),
        "claude-3-5-haiku-20241022": (0.80, 4.00),
        "claude-3-opus-20240229": (15.00, 75.00),
    },
    "gemini": {
        "gemini-1.5-pro": (1.25, 5.00),
        "gemini-1.5-flash": (0.075, 0.30),
        "gemini-2.0-flash": (0.10, 0.40),
    },
}


@dataclass
class UsageRecord:
    client_id: str
    automation_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class UsageTracker:
    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def calculate_cost(
        self, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        pricing = COST_PER_1M_TOKENS[provider][model]
        input_rate, output_rate = pricing
        return round(
            (input_tokens * input_rate / 1_000_000) + (output_tokens * output_rate / 1_000_000),
            6,
        )

    def record(
        self,
        client_id: str,
        automation_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> UsageRecord:
        cost = self.calculate_cost(provider, model, input_tokens, output_tokens)
        usage = UsageRecord(
            client_id=client_id,
            automation_id=automation_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        self.records.append(usage)
        return usage

    def get_client_summary(self, client_id: str) -> dict:
        client_records = [r for r in self.records if r.client_id == client_id]
        if not client_records:
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "avg_latency_ms": 0.0,
            }

        total_cost = sum(r.cost_usd for r in client_records)
        total_input = sum(r.input_tokens for r in client_records)
        total_output = sum(r.output_tokens for r in client_records)
        avg_latency = sum(r.latency_ms for r in client_records) / len(client_records)

        return {
            "total_requests": len(client_records),
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "avg_latency_ms": round(avg_latency, 2),
        }

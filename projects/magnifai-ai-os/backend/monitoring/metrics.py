import uuid
from datetime import UTC, datetime


class MetricsCollector:
    def __init__(self) -> None:
        self._metrics: dict[str, list[dict]] = {}

    def record_metric(self, name: str, value: float, tags: dict | None = None) -> dict:
        if name not in self._metrics:
            self._metrics[name] = []
        entry = {
            "id": str(uuid.uuid4()),
            "name": name,
            "value": value,
            "tags": tags or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._metrics[name].append(entry)
        return entry

    def get_metrics(self, name: str, since: datetime | None = None) -> list[dict]:
        entries = self._metrics.get(name, [])
        if since:
            entries = [e for e in entries if datetime.fromisoformat(e["timestamp"]) >= since]
        return entries

    def get_summary(self, name: str) -> dict:
        entries = self._metrics.get(name, [])
        if not entries:
            return {"name": name, "count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
        values = [e["value"] for e in entries]
        return {
            "name": name,
            "count": len(values),
            "avg": round(sum(values) / len(values), 4),
            "min": min(values),
            "max": max(values),
        }

    def get_all_metric_names(self) -> list[str]:
        return list(self._metrics.keys())

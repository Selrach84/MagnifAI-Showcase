import uuid
from datetime import UTC, datetime


class AlertManager:
    def __init__(self) -> None:
        self._alerts: list[dict] = []

    def check_threshold(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        operator: str = "gt",
    ) -> dict | None:
        triggered = False
        if operator == "gt" and current_value > threshold:
            triggered = True
        elif operator == "lt" and current_value < threshold:
            triggered = True
        elif operator == "gte" and current_value >= threshold:
            triggered = True
        elif operator == "lte" and current_value <= threshold:
            triggered = True
        elif operator == "eq" and current_value == threshold:
            triggered = True

        if not triggered:
            return None

        alert = {
            "id": str(uuid.uuid4()),
            "metric_name": metric_name,
            "current_value": current_value,
            "threshold": threshold,
            "operator": operator,
            "status": "active",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._alerts.append(alert)
        return alert

    def get_alerts(self, status: str | None = None) -> list[dict]:
        if status:
            return [a for a in self._alerts if a["status"] == status]
        return list(self._alerts)

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert["id"] == alert_id:
                alert["status"] = "acknowledged"
                return True
        return False

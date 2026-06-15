"""Monitoring API endpoints."""

from fastapi import APIRouter

from backend.monitoring.alerts import AlertManager
from backend.monitoring.logger import ExecutionLogger
from backend.monitoring.metrics import MetricsCollector

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

logger = ExecutionLogger()
metrics = MetricsCollector()
alerts = AlertManager()


@router.get("/metrics")
async def get_all_metrics():
    names = metrics.get_all_metric_names()
    summaries = {name: metrics.get_summary(name) for name in names}
    return {"metrics": summaries}


@router.get("/metrics/{name}")
async def get_metric(name: str):
    entries = metrics.get_metrics(name)
    summary = metrics.get_summary(name)
    return {"name": name, "entries": entries, "summary": summary}


@router.get("/alerts")
async def get_alerts(status: str | None = None):
    return {"alerts": alerts.get_alerts(status)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    success = alerts.acknowledge_alert(alert_id)
    if not success:
        return {"error": "Alert not found"}
    return {"status": "acknowledged"}


@router.get("/summary")
async def get_summary():
    all_metrics = {name: metrics.get_summary(name) for name in metrics.get_all_metric_names()}
    active_alerts = alerts.get_alerts(status="active")
    return {
        "metrics": all_metrics,
        "active_alerts_count": len(active_alerts),
        "total_alerts": len(alerts.get_alerts()),
    }

from backend.agents.base import AgentResponse
from backend.monitoring.alerts import AlertManager
from backend.monitoring.logger import ExecutionLogger
from backend.monitoring.metrics import MetricsCollector


def _make_response(status="success", output=None, error="", iterations=1, latency_ms=10.0):
    return AgentResponse(
        agent_id="a1",
        status=status,
        output=output or {},
        error=error,
        iterations=iterations,
        latency_ms=latency_ms,
    )


def test_logger_records_execution():
    logger = ExecutionLogger()
    resp = _make_response()
    entry = logger.log_execution("a1", {"prompt": "hi"}, resp, 15.0)
    assert entry["agent_id"] == "a1"
    assert entry["status"] == "success"
    assert entry["duration_ms"] == 15.0


def test_logger_get_history():
    logger = ExecutionLogger()
    logger.log_execution("a1", {}, _make_response(), 10.0)
    logger.log_execution("a2", {}, _make_response(), 20.0)
    logger.log_execution("a1", {}, _make_response(), 30.0)
    history = logger.get_execution_history("a1")
    assert len(history) == 2
    assert all(h["agent_id"] == "a1" for h in history)


def test_logger_get_history_limit():
    logger = ExecutionLogger()
    for _ in range(5):
        logger.log_execution("a1", {}, _make_response(), 10.0)
    history = logger.get_execution_history("a1", limit=2)
    assert len(history) == 2


def test_logger_stats():
    logger = ExecutionLogger()
    logger.log_execution("a1", {}, _make_response("success", latency_ms=10), 10.0)
    logger.log_execution("a1", {}, _make_response("error", latency_ms=20), 20.0)
    stats = logger.get_execution_stats("a1")
    assert stats["total"] == 2
    assert stats["success"] == 1
    assert stats["error"] == 1
    assert stats["avg_latency_ms"] == 15.0


def test_logger_stats_empty():
    logger = ExecutionLogger()
    stats = logger.get_execution_stats("nonexistent")
    assert stats["total"] == 0


def test_metrics_collector():
    mc = MetricsCollector()
    mc.record_metric("agent.execution.time", 100.0, {"agent": "a1"})
    mc.record_metric("agent.execution.time", 200.0, {"agent": "a1"})
    entries = mc.get_metrics("agent.execution.time")
    assert len(entries) == 2
    assert entries[0]["value"] == 100.0


def test_metrics_summary():
    mc = MetricsCollector()
    mc.record_metric("latency", 10.0)
    mc.record_metric("latency", 20.0)
    mc.record_metric("latency", 30.0)
    summary = mc.get_summary("latency")
    assert summary["count"] == 3
    assert summary["avg"] == 20.0
    assert summary["min"] == 10.0
    assert summary["max"] == 30.0


def test_metrics_summary_empty():
    mc = MetricsCollector()
    summary = mc.get_summary("nonexistent")
    assert summary["count"] == 0


def test_metrics_get_all_names():
    mc = MetricsCollector()
    mc.record_metric("m1", 1.0)
    mc.record_metric("m2", 2.0)
    assert set(mc.get_all_metric_names()) == {"m1", "m2"}


def test_alert_manager_creates_alert():
    am = AlertManager()
    alert = am.check_threshold("cpu", 95.0, 90.0, "gt")
    assert alert is not None
    assert alert["status"] == "active"
    assert alert["current_value"] == 95.0


def test_alert_manager_no_trigger():
    am = AlertManager()
    alert = am.check_threshold("cpu", 80.0, 90.0, "gt")
    assert alert is None


def test_alert_manager_acknowledge():
    am = AlertManager()
    alert = am.check_threshold("cpu", 95.0, 90.0, "gt")
    assert alert is not None
    result = am.acknowledge_alert(alert["id"])
    assert result is True
    active = am.get_alerts(status="active")
    assert len(active) == 0
    acked = am.get_alerts(status="acknowledged")
    assert len(acked) == 1


def test_alert_manager_acknowledge_unknown():
    am = AlertManager()
    result = am.acknowledge_alert("nonexistent")
    assert result is False

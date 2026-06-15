"""Tests for LLM usage tracker."""

from datetime import UTC, datetime

import pytest

from backend.llm.tracker import COST_PER_1M_TOKENS, UsageRecord, UsageTracker


def test_cost_per_1m_tokens_has_expected_providers():
    assert "openai" in COST_PER_1M_TOKENS
    assert "claude" in COST_PER_1M_TOKENS
    assert "gemini" in COST_PER_1M_TOKENS


def test_cost_per_1m_tokens_has_model_entries():
    assert "gpt-4o" in COST_PER_1M_TOKENS["openai"]
    assert "claude-3-5-sonnet-20241022" in COST_PER_1M_TOKENS["claude"]
    assert "gemini-1.5-pro" in COST_PER_1M_TOKENS["gemini"]


def test_usage_record_fields():
    record = UsageRecord(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        latency_ms=150.0,
        timestamp=datetime.now(UTC),
    )
    assert record.client_id == "client-1"
    assert record.automation_id == "auto-1"
    assert record.provider == "openai"
    assert record.model == "gpt-4o"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.cost_usd == 0.001
    assert record.latency_ms == 150.0
    assert isinstance(record.timestamp, datetime)


def test_calculate_cost_openai_gpt4o():
    tracker = UsageTracker()
    cost = tracker.calculate_cost("openai", "gpt-4o", input_tokens=1000, output_tokens=500)
    assert cost > 0
    assert isinstance(cost, float)


def test_calculate_cost_claude_sonnet():
    tracker = UsageTracker()
    cost = tracker.calculate_cost(
        "claude", "claude-3-5-sonnet-20241022", input_tokens=1000, output_tokens=500
    )
    assert cost > 0


def test_calculate_cost_gemini_pro():
    tracker = UsageTracker()
    cost = tracker.calculate_cost("gemini", "gemini-1.5-pro", input_tokens=1000, output_tokens=500)
    assert cost > 0


def test_calculate_cost_unknown_provider_raises():
    tracker = UsageTracker()
    with pytest.raises(KeyError):
        tracker.calculate_cost("unknown", "unknown-model", input_tokens=100, output_tokens=100)


def test_calculate_cost_zero_tokens():
    tracker = UsageTracker()
    cost = tracker.calculate_cost("openai", "gpt-4o", input_tokens=0, output_tokens=0)
    assert cost == 0.0


def test_record_creates_usage_record():
    tracker = UsageTracker()
    record = tracker.record(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        latency_ms=120.0,
    )
    assert isinstance(record, UsageRecord)
    assert record.client_id == "client-1"
    assert record.provider == "openai"
    assert record.cost_usd > 0


def test_record_stores_in_history():
    tracker = UsageTracker()
    tracker.record(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        latency_ms=120.0,
    )
    assert len(tracker.records) == 1


def test_get_client_summary_empty():
    tracker = UsageTracker()
    summary = tracker.get_client_summary("nonexistent")
    assert summary["total_requests"] == 0
    assert summary["total_cost_usd"] == 0.0
    assert summary["total_input_tokens"] == 0
    assert summary["total_output_tokens"] == 0


def test_get_client_summary_single_record():
    tracker = UsageTracker()
    tracker.record(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        latency_ms=120.0,
    )
    summary = tracker.get_client_summary("client-1")
    assert summary["total_requests"] == 1
    assert summary["total_cost_usd"] > 0
    assert summary["total_input_tokens"] == 100
    assert summary["total_output_tokens"] == 50
    assert summary["avg_latency_ms"] == 120.0


def test_get_client_summary_multiple_records():
    tracker = UsageTracker()
    tracker.record(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        latency_ms=100.0,
    )
    tracker.record(
        client_id="client-1",
        automation_id="auto-2",
        provider="claude",
        model="claude-3-5-sonnet-20241022",
        input_tokens=200,
        output_tokens=100,
        latency_ms=200.0,
    )
    summary = tracker.get_client_summary("client-1")
    assert summary["total_requests"] == 2
    assert summary["total_input_tokens"] == 300
    assert summary["total_output_tokens"] == 150
    assert summary["avg_latency_ms"] == 150.0
    assert summary["total_cost_usd"] > 0


def test_get_client_summary_filters_by_client():
    tracker = UsageTracker()
    tracker.record(
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        latency_ms=100.0,
    )
    tracker.record(
        client_id="client-2",
        automation_id="auto-2",
        provider="openai",
        model="gpt-4o",
        input_tokens=200,
        output_tokens=100,
        latency_ms=200.0,
    )
    summary = tracker.get_client_summary("client-1")
    assert summary["total_requests"] == 1
    assert summary["total_input_tokens"] == 100

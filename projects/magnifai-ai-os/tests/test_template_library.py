"""Tests for template library (JSON files) and API endpoints."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

LIBRARY_DIR = Path(__file__).parent.parent / "backend" / "templates" / "library"
client = TestClient(app)


def _load_template(name: str) -> dict:
    with open(LIBRARY_DIR / name) as f:
        return json.load(f)


def test_lead_scoring_template():
    data = _load_template("lead-scoring.json")
    assert data["id"] == "lead-scoring-v1"
    assert data["category"] == "lead-scoring"
    assert data["required_llm"] is True
    assert len(data["steps"]) == 4
    assert "source_webhook" in data["config_schema"]["properties"]


def test_email_sequence_template():
    data = _load_template("email-sequence.json")
    assert data["id"] == "email-sequence-v1"
    assert data["category"] == "email"
    assert data["required_llm"] is True
    assert "sender_email" in data["config_schema"]["properties"]


def test_onboarding_template():
    data = _load_template("client-onboarding.json")
    assert data["id"] == "client-onboarding-v1"
    assert data["category"] == "onboarding"
    assert data["required_llm"] is False
    assert "crm" in data["required_connectors"]


def test_data_enrichment_template():
    data = _load_template("data-enrichment.json")
    assert data["id"] == "data-enrichment-v1"
    assert data["category"] == "data"
    assert data["required_llm"] is True


def test_report_generator_template():
    data = _load_template("report-generator.json")
    assert data["id"] == "report-generator-v1"
    assert data["category"] == "report"
    assert data["required_llm"] is True


def test_template_api_list():
    response = client.get("/api/templates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


def test_template_api_list_by_category():
    response = client.get("/api/templates?category=email")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "email"


def test_template_api_get():
    response = client.get("/api/templates/lead-scoring-v1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "lead-scoring-v1"


def test_template_api_get_not_found():
    response = client.get("/api/templates/nonexistent")
    assert response.status_code == 404


def test_template_api_validate():
    response = client.post(
        "/api/templates/lead-scoring-v1/validate",
        json={"config": {"source_webhook": "https://example.com"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_template_api_validate_missing():
    response = client.post(
        "/api/templates/lead-scoring-v1/validate",
        json={"config": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


def test_template_api_render():
    response = client.post(
        "/api/templates/lead-scoring-v1/render",
        json={"config": {"source_webhook": "https://example.com"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["template_id"] == "lead-scoring-v1"
    assert len(data["steps"]) == 4


def test_template_api_render_invalid():
    response = client.post(
        "/api/templates/lead-scoring-v1/render",
        json={"config": {}},
    )
    assert response.status_code == 422


def test_template_api_categories():
    response = client.get("/api/templates/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data["categories"]) == 5

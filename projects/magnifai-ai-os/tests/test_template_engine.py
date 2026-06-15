"""Tests for template engine."""

import pytest

from backend.templates.engine import TemplateEngine


@pytest.fixture
def engine():
    return TemplateEngine()


def test_load_templates(engine):
    assert len(engine.templates) == 5


def test_get_template(engine):
    tpl = engine.get_template("lead-scoring-v1")
    assert tpl.id == "lead-scoring-v1"
    assert tpl.name == "AI Lead Scoring"
    assert tpl.version == "1.0.0"


def test_get_template_not_found(engine):
    with pytest.raises(KeyError, match="Template not found"):
        engine.get_template("nonexistent")


def test_list_templates(engine):
    templates = engine.list_templates()
    assert len(templates) == 5
    assert all("id" in t and "name" in t for t in templates)


def test_list_templates_by_category(engine):
    templates = engine.list_templates(category="email")
    assert len(templates) == 1
    assert templates[0]["category"] == "email"


def test_validate_config_valid(engine):
    valid, errors = engine.validate_config(
        "lead-scoring-v1",
        {"source_webhook": "https://example.com/webhook"},
    )
    assert valid is True
    assert errors == []


def test_validate_config_missing(engine):
    valid, errors = engine.validate_config("lead-scoring-v1", {})
    assert valid is False
    assert len(errors) == 1
    assert "source_webhook" in errors[0]


def test_render_workflow(engine):
    result = engine.render_workflow(
        "lead-scoring-v1",
        {"source_webhook": "https://example.com/webhook"},
    )
    assert result["template_id"] == "lead-scoring-v1"
    assert result["template_version"] == "1.0.0"
    assert len(result["steps"]) == 4
    assert result["config"]["source_webhook"] == "https://example.com/webhook"


def test_render_invalid_config(engine):
    with pytest.raises(ValueError, match="Invalid config"):
        engine.render_workflow("lead-scoring-v1", {})


def test_validate_connectors():
    from backend.templates.validator import TemplateValidator

    errors = TemplateValidator.validate_connectors(["webhook", "email"], ["webhook"])
    assert len(errors) == 1
    assert "email" in errors[0]

    errors = TemplateValidator.validate_connectors(["webhook"], ["webhook", "email"])
    assert errors == []


def test_validate_schema():
    from backend.templates.validator import TemplateValidator

    schema = {
        "properties": {
            "name": {"type": "string", "required": True},
            "count": {"type": "number"},
        }
    }
    errors = TemplateValidator.validate_schema({"name": "test"}, schema)
    assert errors == []

    errors = TemplateValidator.validate_schema({}, schema)
    assert len(errors) == 1

    errors = TemplateValidator.validate_schema({"name": 123}, schema)
    assert len(errors) == 1

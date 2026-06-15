import pytest

from backend.llm.templates.registry import TemplateConfig, TemplateRegistry, VariableConfig


def _make_registry_with_one() -> TemplateRegistry:
    registry = TemplateRegistry()
    registry.templates["demo"] = TemplateConfig(
        id="demo",
        name="Demo Template",
        description="A test template",
        system_message="You are a helpful assistant.",
        user_message_template="Hello {name}, welcome to {place}!",
        variables=[
            VariableConfig(name="name", description="User name"),
            VariableConfig(
                name="place", description="Location", required=True, default="the office"
            ),
        ],
    )
    return registry


class TestTemplateRender:
    def test_template_render(self):
        registry = _make_registry_with_one()
        result = registry.render("demo", {"name": "Alice", "place": "Wonderland"})
        assert result["system_message"] == "You are a helpful assistant."
        assert result["user_message"] == "Hello Alice, welcome to Wonderland!"

    def test_template_uses_default(self):
        registry = _make_registry_with_one()
        result = registry.render("demo", {"name": "Bob"})
        assert result["user_message"] == "Hello Bob, welcome to the office!"

    def test_template_missing_variable(self):
        registry = _make_registry_with_one()
        with pytest.raises(ValueError, match="Missing required variable: name"):
            registry.render("demo", {})


class TestTemplateList:
    def test_template_list(self):
        registry = _make_registry_with_one()
        listing = registry.list_templates()
        assert len(listing) == 1
        assert listing[0]["id"] == "demo"
        assert listing[0]["name"] == "Demo Template"
        assert listing[0]["description"] == "A test template"


class TestGetTemplate:
    def test_get_template(self):
        registry = _make_registry_with_one()
        tpl = registry.get_template("demo")
        assert tpl.id == "demo"
        assert tpl.system_message == "You are a helpful assistant."

    def test_get_template_missing(self):
        registry = _make_registry_with_one()
        with pytest.raises(KeyError, match="Template not found: nonexistent"):
            registry.get_template("nonexistent")

"""Template engine — loads, validates, and renders automation templates."""

import glob
import json
from pathlib import Path

from pydantic import BaseModel


class AutomationTemplate(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str
    required_connectors: list[str] = []
    required_llm: bool = False
    config_schema: dict = {}
    steps: list[dict] = []
    outputs: list[str] = []


class TemplateEngine:
    def __init__(self, templates_dir: str | None = None):
        if templates_dir is None:
            templates_dir = str(Path(__file__).parent / "library")
        self.templates: dict[str, AutomationTemplate] = {}
        self._load_templates(templates_dir)

    def _load_templates(self, path: str) -> None:
        for f in glob.glob(f"{path}/*.json"):
            with open(f) as fp:
                data = json.load(fp)
                tpl = AutomationTemplate(**data)
                self.templates[tpl.id] = tpl

    def get_template(self, template_id: str) -> AutomationTemplate:
        if template_id not in self.templates:
            raise KeyError(f"Template not found: {template_id}")
        return self.templates[template_id]

    def list_templates(self, category: str | None = None) -> list[dict]:
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return [
            {"id": t.id, "name": t.name, "version": t.version, "category": t.category}
            for t in templates
        ]

    def validate_config(self, template_id: str, config: dict) -> tuple[bool, list[str]]:
        tpl = self.get_template(template_id)
        errors: list[str] = []
        for key, schema in tpl.config_schema.get("properties", {}).items():
            if schema.get("required", False) and key not in config:
                errors.append(f"Missing required config: {key}")
        return len(errors) == 0, errors

    def render_workflow(self, template_id: str, config: dict) -> dict:
        tpl = self.get_template(template_id)
        valid, errors = self.validate_config(template_id, config)
        if not valid:
            raise ValueError(f"Invalid config: {errors}")
        return {
            "template_id": tpl.id,
            "template_version": tpl.version,
            "steps": tpl.steps,
            "config": config,
            "outputs": tpl.outputs,
        }

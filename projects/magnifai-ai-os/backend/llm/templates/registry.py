from pydantic import BaseModel


class VariableConfig(BaseModel):
    name: str
    description: str = ""
    required: bool = True
    default: str | None = None


class TemplateConfig(BaseModel):
    id: str
    name: str
    description: str = ""
    system_message: str
    user_message_template: str
    variables: list[VariableConfig]
    provider_preference: list[str] = ["openai", "claude", "gemini"]


class TemplateRegistry:
    def __init__(self, templates_dir: str | None = None):
        self.templates: dict[str, TemplateConfig] = {}
        if templates_dir:
            self._load_templates(templates_dir)

    def _load_templates(self, path: str):
        import glob
        import json

        for f in glob.glob(f"{path}/*.json"):
            with open(f) as fp:
                data = json.load(fp)
                tpl = TemplateConfig(**data)
                self.templates[tpl.id] = tpl

    def render(self, template_id: str, variables: dict) -> dict:
        tpl = self.get_template(template_id)
        rendered_vars = {}
        for var in tpl.variables:
            if var.name in variables:
                rendered_vars[var.name] = variables[var.name]
            elif var.default is not None:
                rendered_vars[var.name] = var.default
            elif var.required:
                raise ValueError(f"Missing required variable: {var.name}")
        user_msg = tpl.user_message_template.format(**rendered_vars)
        return {"system_message": tpl.system_message, "user_message": user_msg}

    def list_templates(self) -> list[dict]:
        return [
            {"id": t.id, "name": t.name, "description": t.description}
            for t in self.templates.values()
        ]

    def get_template(self, template_id: str) -> TemplateConfig:
        if template_id not in self.templates:
            raise KeyError(f"Template not found: {template_id}")
        return self.templates[template_id]

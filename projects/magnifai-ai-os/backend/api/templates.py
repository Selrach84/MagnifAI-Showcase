"""Template management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.templates.engine import TemplateEngine

router = APIRouter(prefix="/api/templates", tags=["templates"])

engine = TemplateEngine()


class ValidateRequest(BaseModel):
    config: dict


class RenderRequest(BaseModel):
    config: dict


@router.get("")
async def list_templates(category: str | None = None):
    return engine.list_templates(category)


@router.get("/categories")
async def list_categories():
    templates = engine.list_templates()
    categories = sorted({t["category"] for t in templates})
    return {"categories": categories}


@router.get("/{template_id}")
async def get_template(template_id: str):
    try:
        tpl = engine.get_template(template_id)
        return tpl.model_dump()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{template_id}/validate")
async def validate_config(template_id: str, request: ValidateRequest):
    try:
        valid, errors = engine.validate_config(template_id, request.config)
        return {"valid": valid, "errors": errors}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{template_id}/render")
async def render_workflow(template_id: str, request: RenderRequest):
    try:
        return engine.render_workflow(template_id, request.config)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

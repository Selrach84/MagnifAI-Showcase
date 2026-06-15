"""MagnifAI AI OS — FastAPI application."""

from fastapi import FastAPI

from backend.api.health import router as health_router

app = FastAPI(
    title="MagnifAI AI OS",
    description="Internal automation delivery platform",
    version="0.1.0",
)

app.include_router(health_router)

try:
    from backend.api.llm import router as llm_router

    app.include_router(llm_router)
except ImportError:
    pass

try:
    from backend.api.connectors import router as connectors_router

    app.include_router(connectors_router)
except ImportError:
    pass

try:
    from backend.api.templates import router as templates_router

    app.include_router(templates_router)
except ImportError:
    pass


@app.get("/")
async def root():
    """Root endpoint with app info."""
    return {
        "name": "magnifai-ai-os",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }

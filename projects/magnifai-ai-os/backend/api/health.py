"""Health check endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from backend.database import engine

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """Check application and database health."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database_status = "connected"
        status = "ok"
    except Exception as e:
        database_status = f"error: {e}"
        status = "degraded"

    return {"status": status, "database": database_status}

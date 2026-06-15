"""Connector management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors import GoHighLevelConnector, N8nConnector
from backend.database import get_db
from backend.models.connector import Connector

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


class ConnectorCreate(BaseModel):
    name: str
    type: str
    credentials: dict = {}
    base_url: str = ""
    enabled: bool = True


class ConnectorUpdate(BaseModel):
    name: str | None = None
    credentials: dict | None = None
    base_url: str | None = None
    enabled: bool | None = None


def _build_connector(connector: Connector):
    """Build the appropriate connector instance from a DB row."""
    creds = {}
    if connector.credentials:
        import json

        creds = json.loads(connector.credentials)

    if connector.type == "n8n":
        return N8nConnector(
            base_url=connector.base_url or "", api_key=creds.get("api_key", "")
        )
    if connector.type == "gohighlevel":
        return GoHighLevelConnector(
            api_key=creds.get("api_key", ""),
            location_id=creds.get("location_id", ""),
        )
    return None


@router.post("")
async def create_connector(
    payload: ConnectorCreate, db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """Create a new connector configuration."""
    import json

    connector = Connector(
        name=payload.name,
        type=payload.type,
        credentials=json.dumps(payload.credentials) if payload.credentials else None,
        base_url=payload.base_url or None,
        enabled=payload.enabled,
    )
    db.add(connector)
    await db.flush()
    return {
        "id": connector.id,
        "name": connector.name,
        "type": connector.type,
        "enabled": connector.enabled,
        "status": connector.status,
    }


@router.get("")
async def list_connectors(db: AsyncSession = Depends(get_db)):  # noqa: B008
    """List all connectors."""
    result = await db.execute(select(Connector))
    connectors = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "enabled": c.enabled,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in connectors
    ]


@router.get("/{connector_id}")
async def get_connector(connector_id: str, db: AsyncSession = Depends(get_db)):  # noqa: B008
    """Get a single connector by ID."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {
        "id": connector.id,
        "name": connector.name,
        "type": connector.type,
        "base_url": connector.base_url,
        "enabled": connector.enabled,
        "status": connector.status,
        "created_at": connector.created_at.isoformat() if connector.created_at else None,
    }


@router.post("/{connector_id}/test")
async def test_connector(connector_id: str, db: AsyncSession = Depends(get_db)):  # noqa: B008
    """Test a connector's connection to the external platform."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    instance = _build_connector(connector)
    if not instance:
        return {"success": False, "error": f"Unsupported connector type: {connector.type}"}

    try:
        ok = await instance.test_connection()
        connector.status = "connected" if ok else "failed"
        connector.last_tested_at = datetime.now(timezone.utc)
        await db.flush()
        return {"success": ok, "connector_id": connector_id, "status": connector.status}
    except Exception as e:
        connector.status = "error"
        await db.flush()
        return {"success": False, "error": str(e)}


@router.delete("/{connector_id}")
async def delete_connector(connector_id: str, db: AsyncSession = Depends(get_db)):  # noqa: B008
    """Delete a connector."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    await db.delete(connector)
    return {"deleted": True, "id": connector_id}

"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """GET /api/health returns 200 with status ok and database key."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        )
    )

    with patch("backend.api.health.engine", mock_engine):
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_db_error(client):
    """GET /api/health returns degraded when database is unreachable."""
    mock_engine = AsyncMock()
    mock_engine.connect = MagicMock(side_effect=Exception("connection refused"))

    with patch("backend.api.health.engine", mock_engine):
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "error" in data["database"]


@pytest.mark.asyncio
async def test_root(client):
    """GET / returns 200 with app info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "magnifai-ai-os"

"""Tests for database module."""

import pytest

from backend.database import async_session_factory, engine


@pytest.mark.asyncio
async def test_engine_creation():
    """Engine is created with correct URL."""
    assert engine is not None
    assert "asyncpg" in str(engine.url)


@pytest.mark.asyncio
async def test_session_factory_creates_session():
    """Session factory creates async sessions."""
    async with async_session_factory() as session:
        result = await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        assert result.scalar() == 1

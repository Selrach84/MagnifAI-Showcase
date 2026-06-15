"""Tests for Settings configuration module."""

import os


def test_settings_loads_from_env(monkeypatch):
    """Settings loads values from environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/testdb")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("APP_ENV", "testing")

    from backend.config import Settings

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://test:test@localhost:5432/testdb"
    assert settings.openai_api_key == "sk-test-key"
    assert settings.app_env == "testing"


def test_settings_defaults():
    """Settings uses correct defaults when explicit values provided."""
    from backend.config import Settings

    os.environ["DATABASE_URL"] = "postgresql+asyncpg://custom:custom@localhost:5432/custom"
    os.environ["APP_ENV"] = "production"

    settings = Settings()

    assert settings.app_debug is True
    assert settings.redis_url == "redis://localhost:6379/0"

    # Clean up
    del os.environ["DATABASE_URL"]
    del os.environ["APP_ENV"]

"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MagnifAI application settings with sensible defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Database
    database_url: str = "postgresql+asyncpg://magnifai:magnifai@localhost:5432/magnifai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # App settings
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"


settings = Settings()

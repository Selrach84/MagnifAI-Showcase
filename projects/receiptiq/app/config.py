"""Central configuration, loaded from environment.

All tunables live here so the rest of the code never reads os.environ directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _env(key: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


def _split(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]


# Provider model defaults (override with <PROVIDER>_MODEL).
_DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


@dataclass(frozen=True)
class Config:
    # --- Telegram ---
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", required=True))
    admin_ids: list[int] = field(default_factory=lambda: _split(_env("ADMIN_TELEGRAM_IDS", "")))

    # --- Vision provider ---
    provider: str = field(default_factory=lambda: (_env("PROVIDER", "gemini") or "gemini").lower())
    gemini_key: str | None = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    openai_key: str | None = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    anthropic_key: str | None = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    # --- Google Sheets ---
    google_creds_file: str = field(
        default_factory=lambda: _env("GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "service_account.json"))
    )
    spreadsheet_id: str | None = field(default_factory=lambda: _env("SPREADSHEET_ID"))

    # --- Image handling ---
    max_image_px: int = field(default_factory=lambda: int(_env("MAX_IMAGE_PX", "1600")))
    jpeg_quality: int = field(default_factory=lambda: int(_env("JPEG_QUALITY", "80")))

    # --- Storage ---
    db_path: str = field(default_factory=lambda: str(DATA_DIR / "receiptiq.db"))

    @property
    def model(self) -> str:
        custom = _env(f"{self.provider.upper()}_MODEL")
        return custom or _DEFAULT_MODELS.get(self.provider, "")

    @property
    def provider_key(self) -> str | None:
        return {
            "gemini": self.gemini_key,
            "openai": self.openai_key,
            "anthropic": self.anthropic_key,
        }.get(self.provider)

    def validate(self) -> None:
        if self.provider not in _DEFAULT_MODELS:
            raise RuntimeError(f"Unknown PROVIDER '{self.provider}'. Use: {', '.join(_DEFAULT_MODELS)}")
        if not self.provider_key:
            raise RuntimeError(f"PROVIDER={self.provider} but its API key env var is not set.")


def load_config() -> Config:
    cfg = Config()
    cfg.validate()
    return cfg

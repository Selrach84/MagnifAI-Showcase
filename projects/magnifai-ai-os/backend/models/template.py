"""Template model — reusable automation templates."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Template:
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    n8n_workflow: Mapped[dict] = mapped_column(JSONB, nullable=False)
    required_connectors: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    estimated_setup_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateVersion:
    __tablename__ = "template_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    config_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    steps: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

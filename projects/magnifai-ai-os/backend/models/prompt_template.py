"""PromptTemplate model — reusable LLM prompt definitions."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class PromptTemplate:
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

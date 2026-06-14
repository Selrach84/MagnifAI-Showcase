"""Structured receipt schema. This is the contract between the LLM and everything downstream."""
from __future__ import annotations

from datetime import date as _date
from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    MEALS = "Meals"
    TRAVEL = "Travel"
    LODGING = "Lodging"
    TRANSPORT = "Transport"
    FUEL = "Fuel"
    GROCERIES = "Groceries"
    OFFICE_SUPPLIES = "Office Supplies"
    SOFTWARE = "Software"
    UTILITIES = "Utilities"
    ENTERTAINMENT = "Entertainment"
    HEALTHCARE = "Healthcare"
    PROFESSIONAL = "Professional Services"
    OTHER = "Other"


def _to_decimal(v):
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return v
    try:
        # strip currency symbols / thousands separators the model may leave in
        s = str(v).replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


class LineItem(BaseModel):
    description: str = ""
    qty: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None

    @field_validator("qty", "unit_price", "amount", mode="before")
    @classmethod
    def _dec(cls, v):
        return _to_decimal(v)


class Receipt(BaseModel):
    merchant: str = "Unknown"
    merchant_address: str | None = None
    date: _date | None = None
    time: str | None = None
    currency: str = "USD"
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    tip: Decimal | None = None
    total: Decimal | None = None
    payment_method: str | None = None
    category: Category = Category.OTHER
    line_items: list[LineItem] = Field(default_factory=list)
    confidence: float = 0.0
    raw_text: str | None = None

    @field_validator("subtotal", "tax", "tip", "total", mode="before")
    @classmethod
    def _dec(cls, v):
        return _to_decimal(v)

    @field_validator("currency", mode="before")
    @classmethod
    def _cur(cls, v):
        if not v:
            return "USD"
        return str(v).strip().upper()[:3]

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        if isinstance(v, Category):
            return v
        if not v:
            return Category.OTHER
        target = str(v).strip().lower()
        for c in Category:
            if c.value.lower() == target:
                return c
        return Category.OTHER

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, f))

    def summary(self) -> str:
        """Human-readable confirmation message for Telegram."""
        d = self.date.isoformat() if self.date else "?"
        lines = [
            f"\U0001F9FE *{self.merchant}*",
            f"\U0001F4C5 {d}   \U0001F3F7 {self.category.value}",
            f"\U0001F4B0 *{self.total} {self.currency}*",
        ]
        if self.tax:
            lines.append(f"   tax: {self.tax}  ·  subtotal: {self.subtotal or '?'}")
        if self.line_items:
            lines.append(f"\U0001F4DD {len(self.line_items)} item(s)")
        lines.append(f"✨ confidence: {int(self.confidence * 100)}%")
        return "\n".join(lines)


# JSON schema description handed to the LLM (kept terse to save tokens).
EXTRACTION_SCHEMA = {
    "merchant": "store/vendor name",
    "merchant_address": "address if visible, else null",
    "date": "purchase date as YYYY-MM-DD, else null",
    "time": "purchase time HH:MM if visible, else null",
    "currency": "ISO 4217 code, infer from symbol/locale, default USD",
    "subtotal": "number or null",
    "tax": "tax/VAT amount as number or null",
    "tip": "tip/gratuity as number or null",
    "total": "grand total as number",
    "payment_method": "e.g. Visa ****1234, Cash, GCash; else null",
    "category": "one of: " + ", ".join(c.value for c in Category),
    "line_items": "array of {description, qty, unit_price, amount}",
    "confidence": "0.0-1.0 your confidence in this extraction",
}

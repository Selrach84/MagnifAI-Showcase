"""Expense categorization.

The LLM already proposes a category. This layer applies deterministic keyword
overrides for well-known merchants so categories stay consistent across clients
regardless of model drift.
"""
from __future__ import annotations

from .models import Category, Receipt

# merchant/keyword -> Category. Lowercase substring match against merchant name.
_RULES: dict[str, Category] = {
    "uber": Category.TRANSPORT,
    "grab": Category.TRANSPORT,
    "lyft": Category.TRANSPORT,
    "shell": Category.FUEL,
    "petron": Category.FUEL,
    "caltex": Category.FUEL,
    "starbucks": Category.MEALS,
    "mcdonald": Category.MEALS,
    "jollibee": Category.MEALS,
    "hotel": Category.LODGING,
    "airbnb": Category.LODGING,
    "marriott": Category.LODGING,
    "airlines": Category.TRAVEL,
    "airways": Category.TRAVEL,
    "cebu pacific": Category.TRAVEL,
    "aws": Category.SOFTWARE,
    "amazon web": Category.SOFTWARE,
    "google cloud": Category.SOFTWARE,
    "openai": Category.SOFTWARE,
    "anthropic": Category.SOFTWARE,
    "notion": Category.SOFTWARE,
    "figma": Category.SOFTWARE,
    "meralco": Category.UTILITIES,
    "pldt": Category.UTILITIES,
    "globe": Category.UTILITIES,
    "netflix": Category.ENTERTAINMENT,
    "spotify": Category.ENTERTAINMENT,
    "pharmacy": Category.HEALTHCARE,
    "mercury drug": Category.HEALTHCARE,
    "grocer": Category.GROCERIES,
    "supermarket": Category.GROCERIES,
    "office": Category.OFFICE_SUPPLIES,
}


def categorize(receipt: Receipt) -> Receipt:
    """Override the model category when a known-merchant rule matches."""
    name = (receipt.merchant or "").lower()
    for keyword, category in _RULES.items():
        if keyword in name:
            receipt.category = category
            break
    return receipt

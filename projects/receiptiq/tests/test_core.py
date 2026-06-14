"""Offline tests — no network, no API keys. Run: python -m pytest tests/ (or python tests/test_core.py)."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.categorize import categorize  # noqa: E402
from app.extractor import _parse_json  # noqa: E402
from app.models import Category, Receipt  # noqa: E402


def test_receipt_parses_messy_llm_output():
    r = Receipt.model_validate(
        {
            "merchant": "Shell Station",
            "date": "2026-05-20",
            "currency": "php",
            "total": "1,250.50",
            "tax": "$150.06",
            "category": "fuel",
            "confidence": 1.7,  # clamps to 1.0
            "line_items": [{"description": "Unleaded", "qty": "1", "amount": "1250.50"}],
        }
    )
    assert r.merchant == "Shell Station"
    assert r.date == date(2026, 5, 20)
    assert r.currency == "PHP"
    assert r.total == Decimal("1250.50")
    assert r.tax == Decimal("150.06")
    assert r.category == Category.FUEL
    assert r.confidence == 1.0
    assert r.line_items[0].amount == Decimal("1250.50")


def test_unknown_category_falls_back_to_other():
    r = Receipt.model_validate({"merchant": "X", "total": "5", "category": "Spaceship Parts"})
    assert r.category == Category.OTHER


def test_categorize_override():
    r = Receipt(merchant="Grab Philippines", total=Decimal("200"), category=Category.OTHER)
    assert categorize(r).category == Category.TRANSPORT


def test_parse_json_tolerates_fences_and_prose():
    assert _parse_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('{"b": 2}') == {"b": 2}


def test_summary_renders():
    r = Receipt(merchant="Cafe", total=Decimal("99"), currency="USD", category=Category.MEALS, confidence=0.9)
    s = r.summary()
    assert "Cafe" in s and "Meals" in s and "90%" in s


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")

"""Ad-hoc CLI: extract a single image without Telegram. Handy for testing the engine.

Usage:  python scripts/scan.py path/to/receipt.jpg
Requires the same env vars as the bot (PROVIDER + key).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.categorize import categorize  # noqa: E402
from app.config import load_config  # noqa: E402
from app.extractor import extract  # noqa: E402


async def _run(path: str) -> None:
    cfg = load_config()
    img = Path(path).read_bytes()
    receipt = categorize(await extract(img, cfg))
    print(receipt.model_dump_json(indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/scan.py <image>")
        raise SystemExit(2)
    asyncio.run(_run(sys.argv[1]))

"""Vision-LLM receipt extraction.

One public coroutine: `extract(image_bytes) -> Receipt`.
Three providers (Gemini / OpenAI / Anthropic) behind a single interface, selected by config.
Raw httpx — no vendor SDKs — to keep the dependency tree and RAM footprint small.
"""
from __future__ import annotations

import base64
import io
import json
import logging

import httpx
from PIL import Image, ImageOps

from .config import Config
from .models import EXTRACTION_SCHEMA, Receipt

log = logging.getLogger("receiptiq.extractor")

_PROMPT = (
    "You are an expert receipt parser. Extract the receipt in the image into JSON "
    "matching EXACTLY this schema (keys and types):\n"
    + json.dumps(EXTRACTION_SCHEMA, indent=2)
    + "\n\nRules:\n"
    "- Output ONLY a single JSON object. No markdown, no prose.\n"
    "- Numbers must be plain (no currency symbols, no thousands separators).\n"
    "- If a field is missing/unreadable use null (except total/merchant — best effort).\n"
    "- Pick the single best category from the allowed list.\n"
    "- Set confidence honestly: low if the photo is blurry/partial.\n"
)


class ExtractionError(Exception):
    pass


def _preprocess(image_bytes: bytes, max_px: int, quality: int) -> tuple[bytes, str]:
    """Downscale + re-encode to JPEG. Cuts upload size, cost, and latency.

    Returns (jpeg_bytes, mime_type). Memory-bounded: one image at a time.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im)  # honor phone rotation
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue(), "image/jpeg"


def _parse_json(text: str) -> dict:
    text = text.strip()
    # tolerate ```json fences or leading prose
    if "```" in text:
        text = text.split("```")[1]
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ExtractionError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(text[start : end + 1])


# --- provider calls: each returns the raw model text -------------------------

async def _call_gemini(client: httpx.AsyncClient, cfg: Config, b64: str, mime: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": _PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}]}],
        "generationConfig": {"temperature": 0, "response_mime_type": "application/json"},
    }
    r = await client.post(url, params={"key": cfg.provider_key}, json=body)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai(client: httpx.AsyncClient, cfg: Config, b64: str, mime: str) -> str:
    body = {
        "model": cfg.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
    }
    r = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg.provider_key}"},
        json=body,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


async def _call_anthropic(client: httpx.AsyncClient, cfg: Config, b64: str, mime: str) -> str:
    body = {
        "model": cfg.model,
        "max_tokens": 1500,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    }
    r = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": cfg.provider_key, "anthropic-version": "2023-06-01"},
        json=body,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


_PROVIDERS = {"gemini": _call_gemini, "openai": _call_openai, "anthropic": _call_anthropic}


async def extract(image_bytes: bytes, cfg: Config, *, retries: int = 2) -> Receipt:
    """Extract a validated Receipt from raw image bytes. Retries on bad JSON."""
    jpeg, mime = _preprocess(image_bytes, cfg.max_image_px, cfg.jpeg_quality)
    b64 = base64.b64encode(jpeg).decode()
    call = _PROVIDERS[cfg.provider]

    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(1, retries + 2):
            try:
                text = await call(client, cfg, b64, mime)
                data = _parse_json(text)
                return Receipt.model_validate(data)
            except (httpx.HTTPError, ExtractionError, json.JSONDecodeError, ValueError) as e:
                last_err = e
                log.warning("extract attempt %d failed: %s", attempt, e)
    raise ExtractionError(f"extraction failed after {retries + 1} tries: {last_err}")

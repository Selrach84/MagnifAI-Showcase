# ReceiptIQ — Design

**Goal:** Receipt-scanning expense system for MagnifAI clients. "100X better than PaddleOCR" *for receipts* — not by re-implementing OCR, but by replacing brittle OCR+regex with vision-LLM structured extraction, wrapped in a real client workflow.

## Why not clone PaddleOCR
- PaddleOCR = general OCR framework (~100k LOC). Detects/recognizes text, returns bounding boxes + strings. You still have to parse those strings into merchant/date/total — the hard, brittle part.
- It needs ~2 GB RAM + ~500 MB model weights. **Will OOM on a 1 GB VPS.**
- For receipts specifically, a vision LLM reads crumpled, rotated, multilingual, low-light receipts and returns *structured fields directly* — higher accuracy, near-zero local RAM (compute is remote), no model maintenance.

## Constraints (from owner)
- Deploy: Ubuntu VPS, **1 GB RAM**, 24 GB disk, alongside Hermes AI.
- Workflow: client signs up → we record their **Telegram ID** → client photographs receipts in a **Telegram bot** → data lands in **Google Sheets** (per client).

## Architecture
```
Client (Telegram) --photo--> Bot (python-telegram-bot, async)
   -> image compress (Pillow)            # shrink before upload = cheaper + faster
   -> Extractor (Vision LLM, provider-agnostic: Gemini | OpenAI | Anthropic)
        -> strict JSON: merchant, date, currency, subtotal, tax, tip, total,
           payment_method, category, line_items[], confidence
   -> Categorizer (LLM category + rule overrides)
   -> Storage (SQLite: clients, receipts, audit, dedup by image hash)
   -> Sheets (gspread: one worksheet tab per client, append row)
   -> Reply to client: parsed summary + inline [Confirm] / [Edit] / [Delete]
```

## Components (one job each)
| File | Responsibility |
|------|----------------|
| `app/config.py` | Env config, provider selection |
| `app/models.py` | `Receipt`, `LineItem` pydantic schema + category enum |
| `app/extractor.py` | image bytes -> validated `Receipt` (3 providers behind one interface) |
| `app/categorize.py` | normalize/override expense category |
| `app/storage.py` | SQLite: clients + receipts + dedup + registry ops |
| `app/sheets.py` | Google Sheets append, per-client worksheet |
| `app/bot.py` | Telegram handlers, admin commands, confirm flow |
| `main.py` | entrypoint / wiring |

## Data model
**Receipt:** merchant, merchant_address?, date (YYYY-MM-DD), time?, currency (ISO-4217), subtotal?, tax?, tip?, total, payment_method?, category, line_items[], confidence(0-1), raw_text?
**LineItem:** description, qty?, unit_price?, amount

**Categories:** Meals, Travel, Lodging, Transport, Fuel, Groceries, Office Supplies, Software, Utilities, Entertainment, Healthcare, Professional Services, Other.

## RAM budget (fits 1 GB)
No torch/paddle/opencv. Deps: python-telegram-bot, httpx, pydantic, Pillow, gspread, google-auth. Idle ~80–120 MB; peak per-image (compress) ~150–200 MB. SQLite (stdlib) for state — no Postgres.

## Provider default
`PROVIDER=gemini` (Gemini Flash: cheapest strong vision, ~$0.0001–0.001/receipt). Switchable to `openai` (gpt-4o-mini) or `anthropic` (claude-haiku) via env. No SDKs — raw httpx keeps deps + RAM minimal.

## Error handling
- Extraction retry (2x) on invalid JSON; on final failure reply "couldn't read, resend clearer photo".
- Dedup: SHA-256 of image bytes -> skip duplicates, tell user.
- Sheets failure: persist locally, mark `synced=0`, retry on next `/sync`.
- Unknown TG ID: bot refuses, tells user to contact MagnifAI.

## Reports
Each client's worksheet IS the live report. Columns: Date, Merchant, Category, Subtotal, Tax, Tip, Total, Currency, Payment, Items, Confidence, ReceiptID. Owner can pivot/sum in Sheets or export. (Phase 2: `/report` generates PDF/period summary.)

## Out of scope (YAGNI for v1)
Web UI, multi-currency conversion, OCR fallback, accounting-software sync. Engine is a clean library — these bolt on later.

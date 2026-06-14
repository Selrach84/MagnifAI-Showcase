# ReceiptIQ — Vision-LLM Receipt Scanner

> Clients snap receipt photos in Telegram → structured data lands in Google Sheets. Built to run on a **1 GB RAM Ubuntu VPS**.

**Stack:** Python · Telegram Bot · Gemini Flash / GPT-4o-mini / Claude Haiku · Google Sheets API · SQLite

## The problem

MagnifAI clients needed expense tracking without learning accounting software. Existing OCR solutions (PaddleOCR, Tesseract) return raw text you have to parse with brittle regex — high complexity, high RAM, low accuracy on crumpled/rotated/multilingual receipts.

## The solution

A vision LLM reads receipt photos directly and returns **structured fields** — no OCR pipeline needed:

```
Client (Telegram) → photo → compress → Vision LLM → JSON
  → categorize → confirm (✅/🗑) → append to client's Google Sheet
```

Each client gets their own worksheet tab. The sheet *is* the live expense report.

## Why vision LLM beats traditional OCR

| Approach | RAM | Accuracy on crumpled/multilingual | Output |
|----------|-----|----------------------------------|--------|
| PaddleOCR | ~2 GB | Poor — regex parsing fragile | Raw text blocks |
| Tesseract | ~500 MB | Poor — needs preprocessing | Raw text |
| **Vision LLM** | ~50 MB | High — reads any photo directly | **Structured JSON fields** |

## Key design decisions

- **Provider-swappable**: Gemini Flash (default, cheapest), GPT-4o-mini, Claude Haiku — pick one, set `PROVIDER`.
- **350 MB memory cap**: systemd unit prevents resource starvation on shared VPS.
- **Admin commands**: `/adduser`, `/clients`, `/removeuser`, `/sync` — full client lifecycle via Telegram.
- **Cost**: ~$0.0001–0.001 per receipt on Gemini Flash. 1,000 receipts/mo ≈ under $1.

## Files

| File | What |
|------|------|
| `main.py` | Bot entrypoint |
| `app/` | Config, models, extractor (vision engine), categorizer, storage, sheets, bot |
| `scripts/install.sh` | VPS deploy script |
| `scripts/scan.py` | CLI test utility |
| `systemd/receiptiq.service` | Systemd unit (350 MB memory cap) |
| `env.example` | Environment template |

## Quick start

```bash
pip install -r requirements.txt
cp env.example .env          # fill TELEGRAM_BOT_TOKEN, PROVIDER, key
python -m pytest tests/ -q   # offline tests
python main.py               # starts the bot
```

## Vitals

- **Cost**: ~$0.0001/receipt on Gemini Flash
- **Infrastructure**: 1 GB RAM VPS (350 MB cap)
- **Users**: Multi-tenant with per-client worksheet tabs
- **Status**: Production-ready · Deployed via systemd

## Test a single receipt (no Telegram needed)

```bash
python scripts/scan.py some_receipt.jpg
```

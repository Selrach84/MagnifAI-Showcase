# LinkedIn AI News Agent

> An autonomous agent that creates daily LinkedIn posts about the latest AI news — sourced from X (Twitter), summarized by AI, and posted with an infographic.

**Stack:** Python · X API v2 · LinkedIn Posts API · SVG Graphics · Cron

## The problem

Maintaining a consistent LinkedIn presence requires daily effort — finding news, writing posts, creating visuals, and publishing. Most professionals either post sporadically or spend hours every week on content.

## The solution

An autonomous Hermes agent that runs daily at 12:00 PM:

1. **Searches** X API v2 for the latest AI news using curated search terms
2. **Summarizes** top stories into a concise, engaging LinkedIn post
3. **Generates** an SVG infographic to accompany the post
4. **Posts** to LinkedIn via the LinkedIn Posts API
5. **Runs** on a cron schedule — zero daily human intervention

## Architecture

```
X API v2 ──> Search recent AI news ──> LLM summarization ──> Post draft
                                                                  │
                                                                  ▼
LinkedIn API <─── SVG infographic <─── Image generator <──────────┘
```

## Files

| File | What |
|------|------|
| `linkedin_ai_news_daily.py` | Main wrapper script with error handling |
| `install-in-hermes.sh` | Hermes agent installation script |
| `run-dry-run-in-hermes.sh` | Dry-run mode (no actual posting) |
| `output/` | Sample generated content (infographic SVG, post drafts, source data) |

## Requirements

- X API v2 Bearer Token
- LinkedIn Access Token + Author URN
- Hermes AI agent runtime

## Setup

```bash
export X_BEARER_TOKEN="your_token"
export LINKEDIN_ACCESS_TOKEN="your_token"
export LINKEDIN_AUTHOR_URN="urn:li:person:xxx"

# Install as Hermes skill
bash install-in-hermes.sh

# Add to cron
/cron add "every day at 12:00 PHT" "daily AI news post" --skill linkedin-ai-news-agent
```

## Dry run

```bash
bash run-dry-run-in-hermes.sh
```

## Sample output

The `output/` directory contains examples of generated content:
- `SVG infographic` — data-vis style image
- `Post draft` — formatted LinkedIn post
- `X Sources JSON` — raw source data

## What this demonstrates

- Social media automation — one cron job replaces a daily manual task
- Multi-API orchestration (X + AI summary + LinkedIn + image generation)
- Hermes agent deployment pattern
- Dry-run capability for safe testing before live posting

## Status

Built · Scaffolded · Ready for deployment

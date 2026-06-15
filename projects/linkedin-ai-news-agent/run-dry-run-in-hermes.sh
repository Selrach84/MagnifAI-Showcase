#!/usr/bin/env bash
set -euo pipefail

SCRIPT="/mnt/c/OBSIDIAN/03 Resources/Skills/linkedin-ai-news-agent/scripts/linkedin_ai_news_agent.py"
OUT="/mnt/c/OBSIDIAN/01 Projects/LinkedIn AI News Agent/output"

python3 "$SCRIPT" --dry-run --out-dir "$OUT"

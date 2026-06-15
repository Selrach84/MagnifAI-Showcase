#!/usr/bin/env bash
set -euo pipefail

VAULT="/mnt/c/OBSIDIAN"
SKILL_SRC="$VAULT/03 Resources/Skills/linkedin-ai-news-agent"
HERMES_SKILL_DIR="$HOME/.hermes/skills/linkedin-ai-news-agent"

mkdir -p "$HERMES_SKILL_DIR"
cp -R "$SKILL_SRC/." "$HERMES_SKILL_DIR/"

echo "Installed linkedin-ai-news-agent skill to $HERMES_SKILL_DIR"

if command -v hermes >/dev/null 2>&1; then
  echo "Hermes found: $(command -v hermes)"
  hermes doctor || true
else
  echo "Hermes command not found in this shell."
  echo "Install Hermes first:"
  echo "curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash"
fi

cat <<'CRON'

After X_BEARER_TOKEN, LINKEDIN_ACCESS_TOKEN, and LINKEDIN_AUTHOR_URN are configured, add this in Hermes:

/cron add "every day at 12:00 Australia/Sydney" "Gather current AI news from X, generate the LinkedIn post and infographic, then publish to LinkedIn if credentials are configured. If publishing fails, save the dry-run files and notify Charles with the error." --skill linkedin-ai-news-agent --workdir "/mnt/c/OBSIDIAN"
CRON

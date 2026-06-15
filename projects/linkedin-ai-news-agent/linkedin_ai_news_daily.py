import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(r"C:\OBSIDIAN\03 Resources\Skills\linkedin-ai-news-agent\scripts\linkedin_ai_news_agent.py")

result = subprocess.run(
    [sys.executable, str(SCRIPT)],
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    print(
        json.dumps(
            {
                "status": "failed",
                "error": result.stderr.strip() or result.stdout.strip(),
                "hint": "Configure X_BEARER_TOKEN, LINKEDIN_ACCESS_TOKEN, and LINKEDIN_AUTHOR_URN in the Hermes runtime environment.",
            },
            indent=2,
        )
    )
    raise SystemExit(result.returncode)

print(result.stdout.strip())

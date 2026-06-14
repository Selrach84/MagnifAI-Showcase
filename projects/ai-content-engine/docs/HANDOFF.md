# Handoff — AI Content Engine v2 (n8n + Claude)

## What it does
A weekly, closed-loop content engine. Every Monday 06:00 it:
1. Reads last week's performance + CRM lead signals.
2. Researches trends/keywords → Claude scores & generates 10 segmented ideas → **human strategy approval**.
3. Claude writes brief → script + blog + social drafts → thumbnail prompts.
4. **Governance gate:** Claude checks brand/SEO, compliance, fact-check. Fails auto-revise ×2, then escalate to a human.
5. Generates assets, assembles a versioned content pack, saves to cloud storage.
6. **One editor approval.**
7. Waits for the recorded video → auto-cuts Shorts/Reels → publishes in parallel to YouTube, WordPress, LinkedIn, Facebook, Instagram, and email — each UTM-tagged.
8. Captures leads to GHL, collects analytics, writes a performance scorecard, posts a Slack digest. **The scorecard feeds next Monday's run — the loop.**

## Files
| File | Purpose |
|------|---------|
| `workflow.n8n.json` | Importable n8n workflow (45 nodes) |
| `env.example.txt` | All env vars + credential map |
| `gen_workflow.py` | Generator (re-run to regenerate the JSON) |
| `client.config.example.json` | Fill-in config for retargeting |
| `docs/HANDOFF.md` | This doc |

## Deploy
1. **Import:** n8n → Workflows → Import from File → `workflow.n8n.json`.
2. **Env:** set variables from `env.example.txt` in n8n.
3. **Credentials:** create one Header Auth credential per `REPLACE_<NAME>`. Open each HTTP node and select the matching credential.
4. **Endpoints:** point `*_ENDPOINT` vars at your connectors.
5. **Webhook video:** post `{videoUrl}` to the resume URL after editing.
6. **Test:** run manually, verify it reaches "Workflow Complete".
7. **Activate:** toggle Active for weekly schedule.

## Kill-switch
- Set env `KILL_SWITCH=true` → next run short-circuits instantly.
- Or toggle workflow Inactive in n8n.
- Both reversible. No data deleted.

## Cost controls
- Per-run token cap via `TOKEN_BUDGET`; per-node `max_tokens` set.
- Weekly cadence → predictable, low run volume.

# AI Content Engine

> Closed-loop AI content automation — research → draft → compliance gate → publish → 7 channels → lead capture → performance score → next cycle.

**Stack:** n8n · Claude API · GoHighLevel · WordPress · YouTube · LinkedIn · Meta · GA4

## The problem

A solar & battery company needed to produce consistent, compliant content across 7+ channels without hiring a full marketing team. Manual content creation was slow, inconsistent, and had no quality or compliance gates.

## The solution

An 8-layer autonomous content pipeline built on n8n (45 nodes) with Claude as the AI engine:

```
Research ──> Draft ──> Quality Gate ──> Compliance Check ──> Multi-Channel Publish
    ↑                                                              │
    └────────────────────────── Lead Capture ←──────────────────────┘
                                        │
                                   Performance Score
                                        │
                                    Next Cycle
```

Each layer is a discrete, testable stage. If any stage fails (e.g. compliance rejects a claim), the pipeline surfaces the issue before anything goes live.

## Key design decisions

- **Config-driven**: Fill `client.config.json` → run generator → get a new workflow. Adding a TikTok channel = one line in config.
- **Compliance-first**: A dedicated Claude-powered compliance gate catches unsupported claims before publishing (critical for regulated industries).
- **Kill-switch**: One webhook stops all publishing without deleting infrastructure.
- **Resource-light**: Runs on a standard VPS. No GPU needed. No expensive SaaS.

## Testing

- 11/11 logic tests pass (mocked — no live credentials needed to verify correctness)
- Test matrix covers: workflow topology, error handling, channel scaling, config generator, compliance gate, kill-switch

## Files

| File | What |
|------|------|
| `workflow.n8n.json` | Importable n8n workflow (45 nodes, 8 layers) |
| `gen_workflow.py` | Config-driven workflow generator |
| `client.config.example.json` | Fill-in config template |
| `env.example.txt` | Environment variables + credential map |
| `docs/HANDOFF.md` | Deploy steps, kill-switch, escalation |

## For the next client

Retarget without rewriting:
1. Copy `client.config.example.json` → `client.config.json`
2. Edit: client name, content segments, target channels, posting cadence, AI model
3. Run `python3 gen_workflow.py` → regenerates the workflow with correct topology
4. Import into n8n, connect credentials, go live

## Status

Built · Tested (11/11) · Ready to deploy · Templated for reuse

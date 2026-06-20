# RTK-Caveman

**Dual-layer token suppression for coding agents.**

A zero-infrastructure skill that combines Rust Token Killer (CLI output compression) with Caveman (response compression) to reduce session token consumption by ~37-40%.

## How it works

```
Bash output ──→ RTK ──→ compressed (49.3% avg savings)
AI responses ──→ Caveman ──→ terse (80% savings)
Both layers ──→ Combined ──→ ~37-40% session savings
```

## Quick start

```
User: "rtk-caveman mode"
Agent: [activates both layers immediately]
```

## Requirements

- `rtk` binary installed (`/opt/homebrew/bin/rtk` via Homebrew)
- Caveman skill loaded (in `~/.claude/skills/caveman/`)

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | Full combined skill definition |
| `TEST-RESULTS.md` | Verified token savings data |
| `README.md` | This file |

## Token savings breakdown

| Source | % of session | Compressed by | Savings on layer |
|---|---|---|---|
| Bash tool output | ~35% | RTK | 49-97% |
| AI responses | ~25% | Caveman | ~80% |
| Fixed overhead | ~40% | Uncompressible | 0% |
| **Total** | **100%** | **Combined** | **~37-40%** |

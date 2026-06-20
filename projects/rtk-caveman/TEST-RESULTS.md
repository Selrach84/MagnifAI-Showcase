# TEST-RESULTS

Date: 2026-06-19
Status: PASS

ps aux: 198815 bytes to 3363 bytes (98.3%).
Historical: 49.3% across 777 commands, 2.3M tokens.
Caveman: active.

## Retest: 2026-06-19 (post-setup)

| Test | Raw | RTK | Savings |
|---|---|---|---|
| `ps aux` | 148,109 bytes | 3,453 bytes | **98%** |
| `git status` | 202 bytes | 37 bytes | **82%** |

## Skill path verification

| Path | Type |
|---|---|
| `~/.claude/skills/rtk-caveman/SKILL.md` | ✅ Symlink → vault |
| `~/.hermes/skills/rtk-caveman/SKILL.md` | ✅ Symlink → vault |

## Auto-load verification

| Tool | Mechanism | Status |
|---|---|---|
| Pi | `~/.pi/agent/AGENTS.md` | ✅ Loads every session |
| Hermes | `rtk-mcp` MCP enabled + `HERMES.md` | ✅ Enabled |

## Caveman verification

Responses in this session are terse — no pleasantries, hedging, or filler. ✅

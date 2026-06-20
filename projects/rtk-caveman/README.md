# RTK-Caveman — Dual-Layer Token Suppression for AI Agents

Reduce session token consumption by **~37-40%** with zero infrastructure changes.

Two layers working together:

```
CLI output ──→ RTK ──→ 49-97% smaller (before agent reads it)
AI responses ──→ Caveman ──→ ~80% shorter (before you read it)
```

## Architecture

```
┌─ Agent Session ──────────────────────────────────────┐
│                                                       │
│  User types:  rtk ps aux                             │
│       │                                              │
│       ▼                                              │
│  ┌─ rtk-mcp-server (Python MCP) ──────────────────┐  │
│  │  Receives: "ps aux"                             │  │
│  │  Runs:     rtk ps aux                           │  │
│  │  Returns:  compressed output (98% savings)      │  │
│  └─────────────────────────────────────────────────┘  │
│       │                                              │
│       ▼                                              │
│  Agent sees compact output, thinks, responds         │
│       │                                              │
│       ▼                                              │
│  ┌─ Caveman Style ─────────────────────────────────┐  │
│  │  No:  "Sure! Let me help you with that..."      │  │
│  │  Yes: "[answer]. [next step]."                   │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

## What's in this project

| File | Purpose |
|---|---|
| `SKILL.md` | Agent skill definition — activates both layers |
| `README.md` | This file — full build & setup guide |
| `TEST-RESULTS.md` | Verified token savings by command type |
| `rtk-mcp-server.py` | MCP server source — pipes commands through RTK |

## Requirements

- macOS (ARM64) or Linux (x86_64)
- Python 3.10+
- Homebrew (for RTK binary)
- Claude Code, Pi, or Hermes agent

---

## Build & Setup

### 1. Install RTK binary

```bash
brew install rtk
```

Verify:

```bash
rtk --version
# → rtk 0.42.4
```

The binary lives at `/opt/homebrew/bin/rtk` (ARM64 Mach-O), built from the [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/master/Formula/r/rtk.rb).

### 2. Install rtk-mcp-server

The server is a single-file Python MCP stdio transport. Copy it to your PATH:

```bash
cp rtk-mcp-server.py ~/.local/bin/rtk-mcp-server
chmod +x ~/.local/bin/rtk-mcp-server
```

Test it:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_command","arguments":{"command":"echo hello"}}}' | python3 ~/.local/bin/rtk-mcp-server
```

### 3. Start the MCP server

The server runs as a background daemon. Start it:

```bash
python3 ~/.local/bin/rtk-mcp-server &
```

Or use persistent launchd (optional):

```bash
# ~/Library/LaunchAgents/com.rtk.mcp.plist
cat > ~/Library/LaunchAgents/com.rtk.mcp.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rtk.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/charlesdenzelsegovia/.local/bin/rtk-mcp-server</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/rtk-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/rtk-mcp.log</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.rtk.mcp.plist
```

### 4. Install Caveman skill

```bash
# The Caveman skill is a standalone file
cp caveman-skill.md ~/.claude/skills/caveman/SKILL.md
```

### 5. Configure your agent

**For Pi (this agent):** Add to `~/.pi/agent/AGENTS.md`:

```markdown
Default mode always uses RTK-Caveman:
- Prefix noisy bash with `rtk`
- Skip `cd`, `export`, `source`
- Lead with answer, no pleasantries
- Fragments OK, technical stays exact
```

**For Claude Code:** Add to `~/.claude/CLAUDE.md`:

```markdown
Use RTK prefix on all shell commands: rtk ps aux, rtk ls -la, etc.
Respond in Caveman mode: terse, no filler, lead with answer.
```

**For Hermes:** Enable the MCP tool in config:

```json
{
  "mcpServers": {
    "rtk": {
      "command": "python3",
      "args": ["/Users/charlesdenzelsegovia/.local/bin/rtk-mcp-server"]
    }
  }
}
```

---

## Usage

### Activate

Say: _"rtk-caveman mode"_ or _"token save mode"_

### Commands

| Without RTK | With RTK | Savings |
|---|---|---|
| `ps aux` | `rtk ps aux` | 98% |
| `ls -la` | `rtk ls -la` | 72-79% |
| `git status` | `rtk git status` | 80-100% |
| `find / -name "*.py"` | `rtk find / -name "*.py"` | 96% |
| `brew list` | `rtk brew list` | 85% |

### Deactivate

Say: _"normal mode"_

---

## Measured Token Savings

### CLI compression (RTK)

| Date | Commands | Raw bytes | RTK bytes | Savings |
|---|---|---|---|---|
| 2026-06-19 | 777 total | — | — | 49.3% avg |
| 2026-06-19 | `ps aux` | 148,109 | 3,453 | **98%** |
| 2026-06-19 | `git status` | 202 | 37 | **82%** |
| 2026-06-19 | Cumulative | ~4.7M | ~2.4M | 2.3M tokens saved |

### Response compression (Caveman)

- ~80% reduction on AI response tokens
- No technical content lost — only pleasantries, hedging, filler

### Combined session savings

| Layer | % of session | Compressed by | Effective savings |
|---|---|---|---|
| CLI tool output | ~35% | RTK 49% avg | ~17% of session |
| AI responses | ~25% | Caveman ~80% | ~20% of session |
| Fixed overhead | ~40% | Uncompressible | 0% |
| **Total** | **100%** | **Combined** | **~37-40%** |

---

## Files

```
rtk-caveman/
├── README.md              ← This file — build & setup guide
├── SKILL.md               ← Agent skill definition (1-page quick reference)
├── TEST-RESULTS.md        ← Verified token savings by command
└── rtk-mcp-server.py      ← MCP server source (164 lines, Python)
```

## Related

- [RTK Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/master/Formula/r/rtk.rb) — Apache 2.0, bottle for ARM64/x86_64
- [Caveman skill](https://github.com/Selrach84/MagnifAI-Showcase/tree/main/projects/caveman) — standalone compression mode
- [Headroom RAG Stack](https://github.com/Selrach84/headroom-rag-stack) — complementary token optimization

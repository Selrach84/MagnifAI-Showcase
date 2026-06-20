# vault-rag v2.6

RAG + Headroom prune + quality gate — **one file, 348 lines.**

| Engine | Savings | How |
|--------|---------|-----|
| RAG (BM25 + graph) | 83-339x on knowledge | FTS5 retrieval → top-K relevant notes |
| Headroom prune | ~88% on operational output | Query-biased relevance keeps only scoring blocks |
| Combined | **100x+ total** | RAG picks *which* notes, Headroom prunes *within* each |
| Quality A/B | ✅ Proven 100% recall | Self-contained quality gate (`quality` cmd) |

## Line count comparison

| Version | Files | Lines | What |
|---------|-------|-------|------|
| v2.5 | 1 | 476 | RAG only |
| v4 | 1 | 900 | RAG + IVF + extra features |
| headroom-stack | 3 | ~300 | RAG + prune + A/B (separate scripts) |
| **v2.6** | **1** | **348** | **RAG + prune + quality + MCP** |

## Usage

```bash
# Build index
python3 vault-rag.py build

# Query with Headroom prune + token report
python3 vault-rag.py query "GHL workflows" --prune --report

# Quality A/B proof (no vault needed)
python3 vault-rag.py quality

# MCP server (for agents)
python3 vault-rag.py serve

# Stats
python3 vault-rag.py stats
```

## Optional: Headroom
`pip install headroom-ai` enables query-relevance pruning + quality gate. Without it, falls back to RAG-only.

## Auto Re-Index (Watch)

The index goes stale as new notes are added. v2.6 has a built-in `watch` command:

```bash
cd /path/to/vault
python3 vault-rag.py watch
```

It polls every **30 seconds** for `.md` file changes (new, modified, or deleted), and auto-rebuilds the index when detected. Zero external dependencies — uses `os.stat()` polling, no `fswatch` or `watchdog` needed.

### One-time run (cron-style)
If you prefer cron instead of a persistent watcher:

**Hermes Cron (0 tokens):**
```bash
hermes cron create \
  --name "vault-rag-reindex" \
  --schedule "0 6 * * *" \
  --no-agent \
  --script "cd /path/to/vault && python3 vault-rag.py build 2>&1 && python3 vault-rag.py stats 2>&1"
```

**System Cron:**
```bash
crontab -e
# Add:
0 6 * * * cd /path/to/vault && python3 vault-rag.py build >> /tmp/vault-rag-build.log 2>&1
```

### Rebuild behavior
- Each rebuild **drops and recreates** the index (no duplicate chunks)
- Vectors are preserved across rebuilds
- Silent on success, prints summary on change

## Why v2.6 > v2.5

v2.5 was **RAG-only** — it found relevant notes but dumped full text.
v2.6 adds **Headroom relevance pruning** — keeps only query-relevant blocks within each note.
Proven: 100% answer recall at half the tokens (see `quality` command).

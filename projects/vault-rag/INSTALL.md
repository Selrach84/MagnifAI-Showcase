---
type: guide
topic: vault-rag
status: draft
last_updated: 2026-06-11
tags: [vault-rag, installation, setup, deployment, automation]
agents: [hermes, claude, opencode, codex]
---

# vault-rag Installation Guide

Install the zero-token, offline RAG engine on any Mac/Linux machine with a Python 3.11+ vault.

## Requirements

| Dependency | Required For | Notes |
|------------|-------------|-------|
| Python 3.11+ | Core engine (BM25, graph, daemon) | macOS: `brew install python@3.11`. Linux: `apt install python3.11` |
| `fastembed` (pip) | Hybrid embeddings (semantic search) | Auto-installed into `.vault-rag/venv/` on `build`. Optional — degrades to BM25-only if absent |
| Obsidian vault | The notes to index | Any folder tree of `.md` files |

**Zero API keys. Zero cloud dependencies. Fully offline.**

## v3 Engine (Recommended)

`vault-rag-v3.py` is the latest version with sub-millisecond query latency:

| Metric | v2 | v3 | Improvement |
|--------|----|----|-------------|
| Cold start (load index) | 1707 ms | 53 ms | **32× faster** |
| Fresh query (warm) | 19 ms | 5 ms | **3.8× faster** |
| Repeat query (cached) | 12 ms | **0.0004 ms** | **30,000× faster** |

**Key upgrades:** binary pickle index + numpy memmap vectors (32× faster cold), IVF cluster search (3.8× faster query), LRU result cache (0-latency repeats), pre-computed IDF, thread-pool daemon for concurrent agents.

## One-Command Install (v3 — Recommended)

```bash
# In the vault directory:
bash Resources/vault-rag/install.sh

# Or specify path:
bash Resources/vault-rag/install.sh /path/to/obsidian/vault
```

This auto-detects Python 3.11+, copies the engine, builds the index, starts the daemon, and runs a test query — all in one command.

## Quick Install (Manual — v3)

```bash
# In the vault root:
python3 vault-rag-v3.py build
python3 vault-rag-v3.py serve --daemon &
python3 vault-rag-v3.py query "what do i have on <topic>" --k 6 --hops 1
```

## v2 (Legacy)

```bash
python3 vault-rag.py build
python3 vault-rag.py serve --daemon &
python3 vault-rag.py query "what do i have on <topic>" --k 6 --hops 1
```

## Step-by-Step

### Step 1: Copy vault-rag to Target Machine

**From source machine (this vault):**
```bash
scp /Volumes/External\ 500\ Gb/OBSIDIAN\ 5.17.26/vault-rag.py user@target:/path/to/vault/
```

**Or copy the whole `.vault-rag/` folder** (if you already built the index and want to skip the build):
```bash
scp -r /Volumes/External\ 500\ Gb/OBSIDIAN\ 5.17.26/.vault-rag user@target:/path/to/vault/
```

### Step 2: Build the Index

```bash
cd /path/to/vault
python3 vault-rag.py build
```

**What this does:**
- Walks all `.md` files in the vault (skips `.git`, `.obsidian`, `.trash`, `node_modules`)
- Extracts `[[wikilinks]]`, frontmatter tags, and body text
- Builds an inverted index (BM25) with field boosting (title×3, tags×2, body×1)
- Chunks long notes (2048-char windows, 256-char overlap)
- Optionally installs `fastembed` into `.vault-rag/venv/` for hybrid embeddings
- Output: `.vault-rag/index.json` (~5MB for 230+ notes)

**Expected output:**
```
built 233 notes, 500 chunks, 225 edges, 58832 terms, hybrid (BM25+384d embeddings) -> .vault-rag/index.json
god nodes: _wiki-hub(38), n8n-wiki(19), ...
```

### Step 3: Start the Warm Daemon

```bash
python3 vault-rag.py serve --daemon &
```

**What this does:**
- Loads the index into memory **once**
- Starts a Unix socket at `.vault-rag/rag.sock`
- Starts a second socket at `.vault-rag/embed.sock` (for embedding model)
- All subsequent queries connect to the socket — zero Python startup, zero file reload
- Sub-millisecond query latency

**Verify it's running:**
```bash
pgrep -f "vault-rag.py serve"
# Returns PID if running
```

### Step 4: Query

```bash
# Human-readable output (default)
python3 vault-rag.py query "n8n docker webhook setup" --k 6 --hops 1

# JSON output (for AI agents)
python3 vault-rag.py query "GHL API custom fields" --k 8 --hops 2 --json

# Machine-optimized output (compact, for AI consumption)
python3 vault-rag.py query "client onboarding automation" --k 6 --hops 1 --agent
```

**Parameters:**

| Flag | Default | Description |
|------|---------|-------------|
| `--k` | 6 | Top-K results to return |
| `--hops` | 1 | Graph expansion hops (0 = exact seeds only, 1 = linked notes, 2 = linked-of-linked) |
| `--json` | false | Output as JSON array instead of formatted text |
| `--agent` | false | Output as compact JSON optimized for AI context (30% of human tokens) |

### Step 5: (Optional) Benchmark

```bash
python3 vault-rag.py bench
```

Sample output:
```
cold  (load + embed + score):   142.50 ms
warm  (embed query + score):     1.234 ms   [x50 avg, fresh query]
warm+ (cached query + score):    0.089 ms   [x500 avg, repeat query]
speedup (cached vs cold):        1600x
```

## Maintenance

### Rebuild After Vault Changes

```bash
python3 vault-rag.py build
```

Do this after adding/editing/deleting notes. The daemon auto-detects a fresh index on next query (stale socket → cold-path fallback → re-register).

### Kill the Daemon

```bash
pkill -f "vault-rag.py serve"
pkill -f "embed_service.py"
```

Then restart with `serve --daemon &` to pick up the new index.

### Check Stats

```bash
python3 vault-rag.py stats
```

Shows node count, hub notes, orphans, cluster sizes, and dangling links.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python3 not found` | Install Python 3.11+: `brew install python@3.11` (macOS) or `apt install python3.11` (Linux) |
| Build hangs | Check for symlink loops in vault. Add to `SKIP_DIRS` in vault-rag.py if needed |
| Daemon won't start | Remove stale socket: `rm -f .vault-rag/rag.sock .vault-rag/embed.sock` |
| Embeddings not working | `fastembed` venv missing. Run `build` again, or use BM25-only mode (query still works) |
| Query returns nothing | Check vault path in vault-rag.py. Ensure `.md` files exist and have content |
| Permission denied | Ensure the user has read access to all vault files and write access to `.vault-rag/` |

## Architecture

```
┌──────────────┐     query ──► ┌──────────────────┐
│  AI Agent     │              │  vault-rag.py      │
│  (Claude/     │ ◄── results  │  ┌──────────────┐  │
│   Hermes/     │              │  │ BM25 scorer   │  │
│   opencode)   │              │  │ (inverted idx)│  │
└──────────────┘              │  ├──────────────┤  │
                              │  │ Graph expander│  │
                              │  │ (wikilinks)   │  │
                              │  ├──────────────┤  │
                              │  │ RRF fuser     │  │
                              │  └──────────────┘  │
                              └──────────┬───────┘
                                         │
                    ┌────────────────────┼────────┐
                    │                    │        │
              ┌─────▼─────┐      ┌──────▼─────┐  │
              │ rag.sock   │      │ embed.sock │  │
              │ (warm BM25)│      │(warm ONNX) │  │
              └───────────┘      └────────────┘  │
                                         │
                              ┌──────────▼───────┐
                              │ .vault-rag/       │
                              │  index.json       │
                              │  embed_service.py │
                              │  venv/ (fastembed)│
                              └──────────────────┘
```

## Install Flowchart

```
bash install.sh /path/to/vault
         │
         ▼
┌─────────────────────┐
│  Detect Python 3.11+│
│  (checks python3.11 │
│   → 3.12 → 3.13 → 3)│
└──────┬──────────────┘
       │ ✗ No Python?
       ▼
┌──────────────────┐
│  ERROR + instruct │
│  to install Python│
└──────────────────┘
       │ ✓ Python found
       ▼
┌─────────────────────┐
│  Verify vault       │
│  (has .md files?)   │
└──────┬──────────────┘
       │ ✗ No .md files
       ▼
┌──────────────────┐
│  ERROR: not a    │
│  valid vault     │
└──────────────────┘
       │ ✓ Vault valid
       ▼
┌─────────────────────────┐
│  Copy / download         │
│  vault-rag.py to vault/ │
└──────────┬──────────────┘
           ▼
┌─────────────────────────────┐
│  python3 vault-rag.py build │
│                             │
│  ┌───────────────────────┐  │
│  │ Walk all .md files    │  │
│  │ Extract wikilinks +   │  │
│  │   tags + body          │  │
│  │ Build inverted index  │  │
│  │   (BM25, field-boosted)│  │
│  │ Chunk notes (2048ch)  │  │
│  │ Auto-install fastembed│  │
│  │   into .vault-rag/venv│  │
│  │ Embed all chunks      │  │
│  │   (384d ONNX, local)  │  │
│  │ Build graph edges     │  │
│  │   from [[wikilinks]]   │  │
│  └───────┬───────────────┘  │
│          ▼                  │
│  ┌──────────────────┐       │
│  │ index.json       │       │
│  │ 235 notes        │       │
│  │ 500 chunks       │       │
│  │ 225 edges        │       │
│  │ 58K terms        │       │
│  │ 512 vectors      │       │
│  └──────────────────┘       │
└──────────┬──────────────────┘
           ▼
┌──────────────────────────────┐
│  python3 vault-rag.py serve  │
│  --daemon &                   │
│                              │
│  ┌────────────────────────┐  │
│  │ Load index.json into   │  │
│  │   memory (once)        │  │
│  │ Start rag.sock         │  │
│  │   (Unix socket)        │  │
│  │ Start embed.sock       │  │
│  │   (ONNX model warm)   │  │
│  │ Prime cache + kill     │  │
│  │   cold-start           │  │
│  └───────┬────────────────┘  │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│  python3 vault-rag.py query  │
│  "n8n webhook docker"        │
│                              │
│  ┌────────────────────────┐  │
│  │ Connect to rag.sock    │  │
│  │  (Unix socket, ~0 net) │  │
│  │                        │  │
│  │ BM25 scorer:           │  │
│  │  O(query_terms *       │  │
│  │    postings)           │  │
│  │                        │  │
│  │ Embed query → cosine   │  │
│  │  via embed.sock        │  │
│  │                        │  │
│  │ RRF fuse BM25 +        │  │
│  │  vectors               │  │
│  │                        │  │
│  │ Graph expansion:       │  │
│  │  1-hop [[wikilinks]]   │  │
│  │                        │  │
│  │ Output: 6 files +      │  │
│  │  17 connected          │  │
│  └────────────────────────┘  │
└──────────────────────────────┘
           ▼
┌──────────────────────────────┐
│  6 file paths returned       │
│  Read only those 6 (~12KB)   │
│  instead of 235 (~470KB)     │
│                              │
│  ✓ ~97% token savings        │
│  ✓ ~12ms response            │
│  ✓ $0 cost                   │
│  ✓ 100% offline              │
└──────────────────────────────┘
```

## Related

- [[CLAUDE.md]] — Vault conventions and RAG layer instructions
- [[vault-rag]] — Usage skill with workflow commands
- [[vault-rag.py]] — The engine itself

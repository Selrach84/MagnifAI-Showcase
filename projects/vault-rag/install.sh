#!/usr/bin/env bash
set -euo pipefail

# ─── vault-rag Installer (v3) ──────────────────────────────────────
# One-command setup: installs vault-rag on any Mac/Linux machine.
# Uses v3 engine by default (binary index, IVF, sub-ms queries).
# Usage: bash install.sh [/path/to/obsidian/vault] [--legacy]
# ─────────────────────────────────────────────────────────────────────

VAULT="${1:-$(pwd)}"
LEGACY=false
if [ "${2:-}" = "--legacy" ]; then LEGACY=true; fi

RAG_PY_NAME="vault-rag-v3.py"
RAG_SRC="https://raw.githubusercontent.com/<YOUR_REPO>/vault-rag/main/${RAG_PY_NAME}"
PYTHON=""

info()  { printf "\033[36m>>\033[0m %s\n" "$*"; }
ok()    { printf "\033[32m OK\033[0m %s\n" "$*"; }
err()   { printf "\033[31m!!\033[0m %s\n" "$*" >&2; exit 1; }

# ── Step 0: detect Python ──
info "Detecting Python 3.11+..."
for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        if awk "BEGIN {exit !($ver >= 3.11)}"; then
            PYTHON="$cmd"
            ok "$($PYTHON --version 2>&1)"
            break
        fi
    fi
done
[ -n "$PYTHON" ] || err "Python 3.11+ required. Install: brew install python@3.11 or apt install python3.11"

# ── Step 1: verify vault ──
info "Checking vault at: $VAULT"
[ -d "$VAULT" ] || err "Not a directory: $VAULT"
MD_COUNT=$(find "$VAULT" -maxdepth 5 -name '*.md' -not -path '*/.git/*' -not -path '*/.obsidian/*' 2>/dev/null | wc -l)
[ "$MD_COUNT" -gt 0 ] || err "No .md files found in $VAULT. Is this an Obsidian vault?"
ok "$MD_COUNT markdown files found"

# ── Step 2: download vault-rag.py (or copy from local) ──
RAG_PY="$VAULT/$RAG_PY_NAME"
# Also try legacy name if --legacy or v3 not found
if $LEGACY; then
    RAG_PY_NAME="vault-rag.py"
    RAG_PY="$VAULT/$RAG_PY_NAME"
fi
if [ -f "$RAG_PY" ]; then
    info "Found $RAG_PY_NAME at $RAG_PY"
elif command -v curl &>/dev/null; then
    info "Downloading $RAG_PY_NAME..."
    curl -fsSL -o "$RAG_PY" "$RAG_SRC" || err "Download failed. Check URL or copy manually."
else
    err "$RAG_PY_NAME not found and curl unavailable. Copy it to $VAULT/ first."
fi

# ── Step 3: build the index ──
info "Building index (BM25 + optional embeddings)..."
cd "$VAULT"
$PYTHON "$RAG_PY" build 2>&1 | head -5
ok "Index built"

# ── Step 4: start warm daemon ──
info "Starting warm daemon..."
$PYTHON "$RAG_PY" serve --daemon &
sleep 1
pgrep -f "$RAG_PY_NAME serve" >/dev/null && ok "Daemon running" || err "Daemon failed to start"

# ── Step 5: test query ──
info "Running test query..."
$PYTHON "$RAG_PY" query "setup installation configuration" --k 3 --hops 0 2>&1 | head -8

echo ""
printf "\033[32m✓ vault-rag installed and running!\033[0m\n"
echo "  Vault:  $VAULT"
echo "  Query:  $PYTHON $RAG_PY query '<your question>' --k 6 --hops 1"
echo "  Rebuild after edits:  $PYTHON $RAG_PY build"

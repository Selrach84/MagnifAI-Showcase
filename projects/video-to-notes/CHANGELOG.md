# Changelog

All notable changes to `claude-watch` are documented here.

## [0.1.0-secure.1] — 2026-05-07 (fork)

Security-hardening fork. See `SECURITY.md` for the full per-fix table.

### Added
- `scripts/security.py` — central URL / local-path validation policy with
  loopback + RFC1918 + link-local + cloud-metadata SSRF block.
- Whisper POST now refuses 3xx redirects (custom `_NoRedirectHandler`) and
  streams the multipart body from a temp file (no full-audio in-memory copy).
- `pyproject.toml` `[project]` section pins a minimum `yt-dlp` version.
- `tests/test_security.py` covers the validator policy.
- `SECURITY.md` documents the threat model + every fix vs upstream.

### Changed
- `https://` is required by default; `http://` refused unless
  `CLAUDE_WATCH_ALLOW_HTTP=1`.
- `copy_local` defaults to copy (was symlink); symlink restored via
  `CLAUDE_WATCH_ALLOW_SYMLINK=1`.
- `~/.config/claude-watch/.env` perms re-applied on every run, with
  `icacls` on Windows in addition to `chmod 0600` on POSIX.
- `--out-dir` and local source paths must resolve under `$HOME`, the
  system temp dir, or `CLAUDE_WATCH_EXTRA_ROOTS` entries.

### Plugin
- Renamed to `claude-watch-secure` to avoid collision with the upstream
  plugin in `~/.claude/plugins/`. Slash command stays `/claude-watch`.

## [0.1.0] — 2026-05-03

### Added
- `/claude-watch <url-or-path> [topic]` slash command that produces structured study notes.
- Scene-aware frame extraction: ffmpeg scene detection (default threshold 0.30) with a coverage floor (synthetic boundaries every 45s across long static gaps) and a budget cap (default 80 frames, drops lowest-scoring detected scenes first; floor boundaries are always preserved).
- Persistent library at `~/claude-watch/library/<slug>/` with cached download, transcript, and scenes — re-runs only regenerate frames + notes.
- Slug rule `YYYY-MM-DD-<title>-<sha1(source+focus)[:4]>` so chronological + collision-safe across focus-range re-watches.
- Native caption pull via yt-dlp (manual + auto-subs) with VTT dedupe.
- Whisper fallback: Groq `whisper-large-v3` (preferred), OpenAI `whisper-1` (alt). Stdlib HTTP clients — no SDKs.
- `--start`/`--end` focused mode with denser coverage floor (15s vs 45s default).
- `setup.py` preflight (`--check` / `--json`) with cross-platform installer (`brew` on macOS auto-runs; `apt`/`dnf`/`winget`/`pip` commands printed elsewhere).
- Three-surface distribution: Claude Code plugin, claude.ai `.skill` bundle (built by `scripts/build-skill.sh`), Codex skill.
- SessionStart hook prints a one-liner only when remediation is needed.
- Strict notes template baked into SKILL.md: TLDR, Key Concepts, per-scene Notes (On screen + Said + Synthesis), Code & Commands, Diagrams Referenced, Open Questions.

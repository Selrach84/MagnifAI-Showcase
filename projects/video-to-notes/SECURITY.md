# SECURITY.md — claude-watch-secure

A hardening fork of [devinilabs/claude-watch](https://github.com/devinilabs/claude-watch). All fixes were derived from a static security review of upstream `main` at fork time. Every fix has a regression test under `tests/`.

## Threat model

`claude-watch` runs as the local user, shells out to `yt-dlp` and `ffmpeg`, and sends audio to a Whisper API. The two realistic threat vectors are:

1. **Agent-driven misuse.** Claude Code itself invokes the plugin with whatever URL or path appears in the prompt. A malicious prompt can request internal URLs (SSRF), arbitrary local paths (read/write), or HTTP URLs (MITM).
2. **Vulnerable transitive tools.** `yt-dlp` has a long history of extractor RCE / file-read CVEs. An unpinned `yt-dlp` on `PATH` is whatever the user happens to have, including stale versions.

Out of scope: protecting against a malicious `yt-dlp`/`ffmpeg` binary already on PATH, protecting against a compromised Whisper provider, or hardening the local OS.

## Fixes vs upstream

| # | Severity | Fix | Where |
|---|---|---|---|
| 1 | High | Windows ACL on `~/.config/claude-watch/.env` (POSIX `chmod 0600` was a no-op on Windows; `icacls /inheritance:r` + per-user grant now applied) | `scripts/security.py:secure_env_file`, `scripts/setup.py:_scaffold_env` |
| 2 | High | `yt-dlp` minimum version pinned in `pyproject.toml` | `pyproject.toml` |
| 3 | Medium | SSRF allow-list — host must resolve to a public IP. Loopback / RFC1918 / link-local / cloud-metadata IPs refused. | `scripts/security.py:validate_url` |
| 4 | Medium | `https://` only by default; `http://` refused unless `CLAUDE_WATCH_ALLOW_HTTP=1` | `scripts/security.py:validate_url` |
| 5 | Medium | `copy_local` defaults to copy (was symlink); symlink only via `CLAUDE_WATCH_ALLOW_SYMLINK=1`. Local source paths must be under `$HOME` or an explicit `CLAUDE_WATCH_EXTRA_ROOTS` entry. | `scripts/security.py:validate_local_path`, `scripts/download.py:copy_local` |
| 6 | Medium | `--out-dir` is validated against the same allow-list, so an agentic caller can't redirect writes to `/etc`, `/var`, sibling user homes, etc. | `scripts/watch.py` |
| 7 | Low | Whisper POST goes through a custom opener that refuses 3xx redirects — closes the cross-host bearer-token leak window on older Pythons. | `scripts/whisper.py:_NoRedirectHandler` |
| 8 | Low | Multipart audio body is streamed from a temp file in 1 MiB chunks instead of `audio.read_bytes()`. Multi-hour audio no longer OOMs the host. | `scripts/whisper.py:_write_multipart`, `_post` |

## Override knobs

These are off by default. Set in the shell or a launcher; never in shared configs.

| Variable | Effect |
|---|---|
| `CLAUDE_WATCH_ALLOW_HTTP=1` | Allow `http://` URLs (offline labs, internal mirrors). |
| `CLAUDE_WATCH_ALLOW_PRIVATE=1` | Allow URLs whose host resolves to a private/loopback IP. |
| `CLAUDE_WATCH_ALLOW_SYMLINK=1` | Restore upstream's symlink-by-default behavior in `copy_local`. |
| `CLAUDE_WATCH_EXTRA_ROOTS=/path1;/path2` | Extra allowed roots for local-path inputs and `--out-dir`. Semicolon on Windows, colon elsewhere. |
| `CLAUDE_WATCH_NO_TEMP_ROOT=1` | Drop the system temp dir from the default allow-list. |

## Reporting

This is a personal fork. If you find a bug here, open an issue against this fork. If you find one that also affects upstream, file there too.

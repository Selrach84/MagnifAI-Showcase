"""yt-dlp download wrapper + local file linker."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from scripts.security import validate_url, validate_local_path


def download_video(url: str, out_dir: Path, *, basename: str = "video") -> Path:
    """Download to `out_dir/<basename>.<ext>` via yt-dlp. Returns the downloaded file."""
    validate_url(url)  # https-only + SSRF block
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / f"{basename}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "best[ext=mp4]/best",
        "-o", template,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {proc.stderr.strip()}")
    matches = sorted(out_dir.glob(f"{basename}.*"))
    if not matches:
        raise RuntimeError(f"yt-dlp returned 0 but no {basename}.* file in {out_dir}")
    return matches[0]


def copy_local(src: Path, out_dir: Path, *, basename: str = "video") -> Path:
    """For local sources, copy into out_dir/<basename>.<ext>.

    The path is validated against the allow-list (default: $HOME) so an
    agentic caller cannot point us at arbitrary filesystem locations. We
    also collapse symlinks via Path.resolve() before copying — the work
    dir gets a regular file, never a symlink that could later be followed
    to attacker-controlled storage.

    Set CLAUDE_WATCH_ALLOW_SYMLINK=1 to opt back into the old symlink
    behavior (still resolved, still validated).
    """
    src = validate_local_path(src, must_exist=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{basename}{src.suffix}"
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if os.environ.get("CLAUDE_WATCH_ALLOW_SYMLINK", "").strip() in {"1", "true", "yes", "on"}:
        try:
            os.symlink(src, dst)
            return dst
        except OSError:
            pass  # fall through to copy
    shutil.copyfile(src, dst)
    return dst

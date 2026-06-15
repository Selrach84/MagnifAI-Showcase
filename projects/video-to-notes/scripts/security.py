"""Centralized URL/path validation for claude-watch.

Goals:
    1. URLs must be https. http:// is refused (MITM exposure on probe/captions).
    2. Hosts must resolve to a public IP. Loopback / RFC1918 / link-local /
       cloud-metadata IPs are refused (SSRF block — yt-dlp/ffmpeg are happy
       to chase internal URLs otherwise).
    3. Local paths used as a source or as --out-dir must live under an allowed
       root (default: $HOME). Paths outside the allow-list are refused so an
       agentic caller cannot point us at /etc, /var, or sibling user homes.

Override knobs (env, off by default):
    CLAUDE_WATCH_ALLOW_HTTP=1         allow http:// URLs (for offline labs)
    CLAUDE_WATCH_ALLOW_PRIVATE=1      allow RFC1918/loopback/link-local hosts
    CLAUDE_WATCH_EXTRA_ROOTS=path1;path2  extra allowed local-path roots
"""
from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


class SecurityError(ValueError):
    """Raised when a URL or path violates the validation policy."""


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _allowed_roots() -> list[Path]:
    roots: list[Path] = [Path.home().resolve()]
    # System temp is included by default — it's user-scoped on Windows and
    # sticky-bit-protected on POSIX. Users who want stricter behavior can
    # set CLAUDE_WATCH_NO_TEMP_ROOT=1.
    if not _truthy("CLAUDE_WATCH_NO_TEMP_ROOT"):
        try:
            roots.append(Path(tempfile.gettempdir()).resolve())
        except OSError:
            pass
    extra = os.environ.get("CLAUDE_WATCH_EXTRA_ROOTS", "")
    if extra:
        sep = ";" if os.name == "nt" else ":"
        for raw in extra.split(sep):
            raw = raw.strip()
            if raw:
                roots.append(Path(raw).expanduser().resolve())
    return roots


def _ip_is_internal(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable → refuse
    if addr.is_loopback or addr.is_link_local or addr.is_private:
        return True
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return True
    # AWS / GCP / Azure metadata service
    if ip in {"169.254.169.254", "fd00:ec2::254"}:
        return True
    return False


def _resolve_host(host: str) -> Iterable[str]:
    """Return all IPs the host resolves to. Empty iter on resolution failure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    return {info[4][0] for info in infos}


def validate_url(url: str) -> str:
    """Reject http://, internal hosts, and unparseable URLs.

    Returns the url unchanged on success. Raises SecurityError otherwise.
    """
    if not isinstance(url, str) or not url:
        raise SecurityError("empty URL")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise SecurityError(f"unsupported URL scheme: {scheme!r}")
    if scheme == "http" and not _truthy("CLAUDE_WATCH_ALLOW_HTTP"):
        raise SecurityError(
            "http:// is refused; use https:// "
            "(set CLAUDE_WATCH_ALLOW_HTTP=1 to override)"
        )
    host = parsed.hostname
    if not host:
        raise SecurityError(f"URL has no host: {url!r}")
    if _truthy("CLAUDE_WATCH_ALLOW_PRIVATE"):
        return url
    # Direct IP literal
    try:
        ipaddress.ip_address(host)
        if _ip_is_internal(host):
            raise SecurityError(
                f"refusing internal/private IP host: {host} "
                "(set CLAUDE_WATCH_ALLOW_PRIVATE=1 to override)"
            )
        return url
    except ValueError:
        pass
    ips = list(_resolve_host(host))
    if not ips:
        raise SecurityError(f"could not resolve host {host!r}")
    bad = [ip for ip in ips if _ip_is_internal(ip)]
    if bad:
        raise SecurityError(
            f"host {host!r} resolves to internal IP(s) {bad}; "
            "refusing (set CLAUDE_WATCH_ALLOW_PRIVATE=1 to override)"
        )
    return url


def validate_local_path(path: str | Path, *, must_exist: bool = True) -> Path:
    """Reject paths outside allowed roots.

    Returns the resolved Path on success. Raises SecurityError otherwise.
    """
    p = Path(path).expanduser().resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"local file not found: {p}")
    roots = _allowed_roots()
    for root in roots:
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise SecurityError(
        f"path {p} is outside allowed roots {roots}; "
        "set CLAUDE_WATCH_EXTRA_ROOTS to add more (semicolon-separated on Windows, "
        "colon-separated elsewhere)"
    )


def secure_env_file(path: Path) -> None:
    """Best-effort restrict an env file to the current user.

    POSIX: chmod 0600.
    Windows: icacls — remove inheritance, grant only the current user Read/Write.

    Failures are swallowed with a stderr warning so setup never hard-fails on
    perms — the goal is best-effort defense in depth, not a hard gate.
    """
    import platform
    import subprocess
    import sys

    path = Path(path)
    if not path.exists():
        return
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            print(f"[claude-watch] warning: chmod 0600 failed on {path}: {e}",
                  file=sys.stderr)
        return
    if platform.system().lower() != "windows":
        return
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        print(f"[claude-watch] warning: USERNAME unset; skipping ACL on {path}",
              file=sys.stderr)
        return
    try:
        # Strip inherited ACEs, then grant only current user Read+Write.
        subprocess.run(
            ["icacls", str(path), "/inheritance:r"],
            check=False, capture_output=True,
        )
        subprocess.run(
            ["icacls", str(path), "/grant:r", f"{user}:(R,W)"],
            check=False, capture_output=True,
        )
    except (FileNotFoundError, OSError) as e:
        print(f"[claude-watch] warning: icacls failed on {path}: {e}",
              file=sys.stderr)

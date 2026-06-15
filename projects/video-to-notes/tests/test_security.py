"""Tests for scripts/security.py — URL/path validation policy."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.security import (
    SecurityError,
    validate_url,
    validate_local_path,
)


def _no_env(*names: str):
    """Pop each env var so the test runs against the default policy."""
    return patch.dict(os.environ, {n: "" for n in names}, clear=False)


# ---- URL scheme ----

def test_validate_url_accepts_https_public_host():
    # We only validate the policy decision here, not DNS — patch the resolver.
    with patch("scripts.security._resolve_host", return_value=["8.8.8.8"]):
        assert validate_url("https://example.com/path") == "https://example.com/path"


def test_validate_url_rejects_http_by_default():
    with _no_env("CLAUDE_WATCH_ALLOW_HTTP"):
        with pytest.raises(SecurityError, match="http"):
            validate_url("http://example.com/v.mp4")


def test_validate_url_allows_http_when_override_set(monkeypatch):
    monkeypatch.setenv("CLAUDE_WATCH_ALLOW_HTTP", "1")
    with patch("scripts.security._resolve_host", return_value=["8.8.8.8"]):
        assert validate_url("http://example.com/v.mp4")


def test_validate_url_rejects_unknown_scheme():
    with pytest.raises(SecurityError):
        validate_url("file:///etc/passwd")
    with pytest.raises(SecurityError):
        validate_url("ftp://example.com/")


def test_validate_url_rejects_empty_or_hostless():
    with pytest.raises(SecurityError):
        validate_url("")
    with pytest.raises(SecurityError):
        validate_url("https:///no-host")


# ---- SSRF block ----

@pytest.mark.parametrize("ip", [
    "127.0.0.1",       # loopback
    "10.0.0.1",        # RFC1918
    "192.168.1.1",     # RFC1918
    "172.16.0.1",      # RFC1918
    "169.254.169.254", # AWS metadata
    "::1",             # IPv6 loopback
    "fe80::1",         # IPv6 link-local
])
def test_validate_url_rejects_internal_ip_literal(ip):
    with _no_env("CLAUDE_WATCH_ALLOW_PRIVATE"):
        with pytest.raises(SecurityError):
            validate_url(f"https://{ip}/x")


def test_validate_url_rejects_host_resolving_to_private_ip():
    with patch("scripts.security._resolve_host", return_value=["10.0.0.5"]):
        with _no_env("CLAUDE_WATCH_ALLOW_PRIVATE"):
            with pytest.raises(SecurityError, match="internal"):
                validate_url("https://internal.corp/x")


def test_validate_url_rejects_unresolvable_host():
    with patch("scripts.security._resolve_host", return_value=[]):
        with pytest.raises(SecurityError, match="resolve"):
            validate_url("https://nonexistent.invalid/x")


def test_validate_url_allows_private_when_override_set(monkeypatch):
    monkeypatch.setenv("CLAUDE_WATCH_ALLOW_PRIVATE", "1")
    assert validate_url("https://10.0.0.1/x")


# ---- Path allow-list ----

def test_validate_local_path_allows_path_under_home(tmp_path, monkeypatch):
    """tmp_path lives under the system temp dir which is in the default
    allow-list, so this should resolve cleanly."""
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    p = validate_local_path(str(f))
    assert p == f.resolve()


def test_validate_local_path_rejects_path_outside_allowed_roots(tmp_path, monkeypatch):
    """Disable the temp-dir default + ensure the path isn't under HOME."""
    monkeypatch.setenv("CLAUDE_WATCH_NO_TEMP_ROOT", "1")
    # Use a path that is provably outside HOME on every supported OS.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    with pytest.raises(SecurityError, match="outside allowed"):
        validate_local_path(str(outside))


def test_validate_local_path_extra_root_grants_access(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_WATCH_NO_TEMP_ROOT", "1")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "h"))
    (tmp_path / "h").mkdir()
    outside = tmp_path / "extra" / "v.mp4"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    sep = ";" if os.name == "nt" else ":"
    monkeypatch.setenv("CLAUDE_WATCH_EXTRA_ROOTS", str(tmp_path / "extra"))
    p = validate_local_path(str(outside))
    assert p == outside.resolve()


def test_validate_local_path_must_exist_default(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_local_path(str(tmp_path / "nope.mp4"))


def test_validate_local_path_must_exist_false_skips_existence_check(tmp_path):
    p = validate_local_path(str(tmp_path / "future.mp4"), must_exist=False)
    assert p == (tmp_path / "future.mp4").resolve()

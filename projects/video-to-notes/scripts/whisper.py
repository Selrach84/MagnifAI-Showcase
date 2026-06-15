"""Stdlib HTTP clients for Groq and OpenAI Whisper APIs.

Security choices:
    - Multipart body is streamed from a temp file (not read into memory) so
      multi-hour transcripts don't OOM the host.
    - The opener used for Whisper POSTs refuses redirects. Bearer-token POSTs
      that follow a 3xx to a different host can leak the Authorization header
      on older Pythons; refusing redirects is simpler than auditing per-version.
"""
from __future__ import annotations

import io
import json
import mimetypes
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
    urlopen,
)


GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = "whisper-1"


class WhisperError(Exception):
    pass


class _NoRedirectHandler(HTTPRedirectHandler):
    """Refuse any 3xx. Whisper endpoints don't redirect under normal use; if
    one does, we'd rather fail loudly than silently chase to a host that
    might receive the Authorization header."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401, N802
        raise HTTPError(req.full_url, code, f"refusing redirect to {newurl}", headers, fp)


def _no_redirect_opener():
    return build_opener(_NoRedirectHandler(), HTTPSHandler())


def pick_backend(
    *,
    groq_key: Optional[str],
    openai_key: Optional[str],
    forced: Optional[str],
) -> Optional[str]:
    """Return 'groq', 'openai', or None.

    Forced backend wins iff its key is present. Otherwise prefer Groq, then OpenAI.
    """
    if forced == "groq":
        return "groq" if groq_key else None
    if forced == "openai":
        return "openai" if openai_key else None
    if groq_key:
        return "groq"
    if openai_key:
        return "openai"
    return None


def _write_multipart(audio: Path, model: str, sink) -> tuple[int, str]:
    """Stream a multipart/form-data body into `sink` (a writable binary file).

    Returns (total_bytes_written, boundary). Audio is streamed in 1 MiB chunks
    so we never hold the whole file in memory.
    """
    boundary = f"----whisper-{uuid.uuid4().hex}"
    crlf = b"\r\n"
    written = 0

    def w(data: bytes) -> None:
        nonlocal written
        sink.write(data)
        written += len(data)

    # Field: model
    w(f"--{boundary}".encode() + crlf)
    w(b'Content-Disposition: form-data; name="model"' + crlf + crlf)
    w(model.encode() + crlf)
    # Field: response_format
    w(f"--{boundary}".encode() + crlf)
    w(b'Content-Disposition: form-data; name="response_format"' + crlf + crlf)
    w(b"verbose_json" + crlf)
    # Field: file (streamed)
    mime = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
    w(f"--{boundary}".encode() + crlf)
    w(
        f'Content-Disposition: form-data; name="file"; filename="{audio.name}"'.encode()
        + crlf
    )
    w(f"Content-Type: {mime}".encode() + crlf + crlf)
    with open(audio, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            w(chunk)
    w(crlf)
    w(f"--{boundary}--".encode() + crlf)
    return written, boundary


def _build_multipart(audio: Path, model: str) -> tuple[bytes, str]:
    """In-memory multipart builder.

    Kept for backwards compatibility with existing tests. New code should use
    the streaming `_write_multipart` path inside `_post`.
    """
    buf = io.BytesIO()
    _, boundary = _write_multipart(audio, model, buf)
    return buf.getvalue(), boundary


def _post(url: str, audio: Path, *, model: str, api_key: str) -> list[dict]:
    """POST audio + model + response_format=verbose_json to a Whisper endpoint.

    Streams the multipart body via a temp file so large audio doesn't OOM.
    Refuses 3xx redirects on the request.

    Returns: [{"t_start": float, "t_end": float, "text": str}, ...]
    Raises: WhisperError on any network, HTTP, JSON, or response-shape failure.
    """
    with tempfile.TemporaryFile() as body_file:
        body_len, boundary = _write_multipart(audio, model, body_file)
        body_file.seek(0)
        req = Request(
            url,
            data=body_file,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(body_len),
            },
        )
        try:
            opener = _no_redirect_opener()
            with opener.open(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            segs = payload.get("segments") or []
            return [
                {
                    "t_start": float(s["start"]),
                    "t_end": float(s["end"]),
                    "text": s["text"].strip(),
                }
                for s in segs
            ]
        except HTTPError as e:
            # Surface the API's JSON error body so users see "Invalid API Key" etc.
            # The response body is small and from the API host; we already refuse
            # redirects so it can't be attacker-substituted via a 3xx.
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            raise WhisperError(f"HTTP {e.code} {e.reason}: {detail}") from e
        except Exception as e:
            # Network, JSON parse, missing keys on segments — all surface as WhisperError.
            raise WhisperError(str(e)) from e


def transcribe_groq(audio: Path, *, api_key: str) -> list[dict]:
    return _post(GROQ_URL, audio, model=GROQ_MODEL, api_key=api_key)


def transcribe_openai(audio: Path, *, api_key: str) -> list[dict]:
    return _post(OPENAI_URL, audio, model=OPENAI_MODEL, api_key=api_key)

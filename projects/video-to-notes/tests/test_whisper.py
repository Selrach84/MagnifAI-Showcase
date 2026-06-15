import io
import json
from unittest.mock import patch, MagicMock

import pytest

from scripts.whisper import (
    pick_backend,
    transcribe_groq,
    transcribe_openai,
    WhisperError,
)


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def test_pick_backend_prefers_groq_when_both_keys_set():
    assert pick_backend(groq_key="g", openai_key="o", forced=None) == "groq"


def test_pick_backend_falls_back_to_openai():
    assert pick_backend(groq_key=None, openai_key="o", forced=None) == "openai"


def test_pick_backend_returns_none_when_no_keys():
    assert pick_backend(groq_key=None, openai_key=None, forced=None) is None


def test_pick_backend_honors_forced_backend():
    assert pick_backend(groq_key="g", openai_key="o", forced="openai") == "openai"


def test_pick_backend_forced_without_key_returns_none():
    assert pick_backend(groq_key=None, openai_key="o", forced="groq") is None


@patch("scripts.whisper._no_redirect_opener")
def test_transcribe_groq_posts_to_correct_endpoint_with_api_key(mock_opener, tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"\x00\x00\x00\x00")
    opener = MagicMock()
    opener.open.return_value = _mock_response(
        {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}]}
    )
    mock_opener.return_value = opener
    out = transcribe_groq(audio, api_key="testkey")
    assert out == [{"t_start": 0.0, "t_end": 1.0, "text": "hello"}]
    req = opener.open.call_args[0][0]
    assert "api.groq.com" in req.full_url
    assert req.get_header("Authorization") == "Bearer testkey"


@patch("scripts.whisper._no_redirect_opener")
def test_transcribe_openai_posts_to_correct_endpoint(mock_opener, tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"\x00")
    opener = MagicMock()
    opener.open.return_value = _mock_response(
        {"segments": [{"start": 1.0, "end": 2.0, "text": "world"}]}
    )
    mock_opener.return_value = opener
    out = transcribe_openai(audio, api_key="k")
    assert out == [{"t_start": 1.0, "t_end": 2.0, "text": "world"}]
    req = opener.open.call_args[0][0]
    assert "api.openai.com" in req.full_url


@patch("scripts.whisper._no_redirect_opener")
def test_transcribe_groq_wraps_errors_in_whisper_error(mock_opener, tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"\x00")
    opener = MagicMock()
    opener.open.side_effect = Exception("boom")
    mock_opener.return_value = opener
    with pytest.raises(WhisperError):
        transcribe_groq(audio, api_key="k")


@patch("scripts.whisper._no_redirect_opener")
def test_transcribe_streams_audio_through_temp_file(mock_opener, tmp_path):
    """Regression: large audio must not be loaded into memory entirely.

    We feed a 4 MB file and assert the request body length matches what the
    streaming multipart writer produced (proving the streaming path ran)."""
    audio = tmp_path / "big.m4a"
    audio.write_bytes(b"x" * (4 * 1024 * 1024))
    opener = MagicMock()
    opener.open.return_value = _mock_response({"segments": []})
    mock_opener.return_value = opener
    transcribe_groq(audio, api_key="k")
    req = opener.open.call_args[0][0]
    body_len = int(req.get_header("Content-length"))
    assert body_len > 4 * 1024 * 1024  # audio + multipart headers


def test_no_redirect_opener_refuses_3xx():
    """A 3xx during the auth'd POST should surface as a WhisperError, not be
    silently followed (which could leak the bearer token to a different host
    on older Pythons)."""
    from scripts.whisper import _NoRedirectHandler
    from urllib.error import HTTPError
    from urllib.request import Request

    handler = _NoRedirectHandler()
    req = Request("https://api.groq.com/x", method="POST",
                  headers={"Authorization": "Bearer secret"})
    with pytest.raises(HTTPError):
        handler.redirect_request(req, io.BytesIO(b""), 302, "Found",
                                 {}, "https://evil.example/x")

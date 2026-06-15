"""Tests for unified LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.llm.config import LLMConfig, ProviderConfig
from backend.llm.providers.base import LLMResponse


def _make_config():
    return LLMConfig(
        openai=ProviderConfig(api_key="openai-key", default_model="gpt-4o"),
        claude=ProviderConfig(api_key="claude-key", default_model="claude-3-5-sonnet-20241022"),
    )


def _mock_response(provider="openai", model="gpt-4o"):
    return LLMResponse(
        content="Hello!",
        model=model,
        provider=provider,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        finish_reason="stop",
        latency_ms=100.0,
    )


@patch("backend.llm.client.OpenAIProvider")
def test_client_initializes_providers_from_config(mock_openai_cls):
    from backend.llm.client import LLMClient

    mock_openai_cls.return_value = AsyncMock()
    config = _make_config()
    client = LLMClient(config)

    assert "openai" in client._providers
    assert "claude" in client._providers
    assert "gemini" not in client._providers
    mock_openai_cls.assert_called_once_with(api_key="openai-key", default_model="gpt-4o")


@pytest.mark.asyncio
@patch("backend.llm.client.ClaudeProvider")
@patch("backend.llm.client.OpenAIProvider")
async def test_chat_uses_primary_provider(mock_openai_cls, mock_claude_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_openai_inst.chat = AsyncMock(return_value=_mock_response("openai", "gpt-4o"))
    mock_openai_cls.return_value = mock_openai_inst

    mock_claude_inst = AsyncMock()
    mock_claude_cls.return_value = mock_claude_inst

    client = LLMClient(_make_config())
    result = await client.chat(
        messages=[{"role": "user", "content": "Hi"}],
        provider="openai",
    )

    assert result.provider == "openai"
    mock_openai_inst.chat.assert_called_once()


@pytest.mark.asyncio
@patch("backend.llm.client.ClaudeProvider")
@patch("backend.llm.client.OpenAIProvider")
async def test_chat_falls_back_on_primary_failure(mock_openai_cls, mock_claude_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_openai_inst.chat = AsyncMock(side_effect=Exception("rate limit"))
    mock_openai_cls.return_value = mock_openai_inst

    mock_claude_inst = AsyncMock()
    mock_claude_inst.chat = AsyncMock(
        return_value=_mock_response("claude", "claude-3-5-sonnet-20241022")
    )
    mock_claude_cls.return_value = mock_claude_inst

    config = LLMConfig(
        openai=ProviderConfig(api_key="openai-key"),
        claude=ProviderConfig(api_key="claude-key"),
        auto_provider_preference=["openai", "claude"],
    )
    client = LLMClient(config)
    result = await client.chat(messages=[{"role": "user", "content": "Hi"}])

    assert result.provider == "claude"
    mock_claude_inst.chat.assert_called_once()


@pytest.mark.asyncio
@patch("backend.llm.client.ClaudeProvider")
@patch("backend.llm.client.OpenAIProvider")
async def test_chat_raises_when_all_providers_fail(mock_openai_cls, mock_claude_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_openai_inst.chat = AsyncMock(side_effect=Exception("openai down"))
    mock_openai_cls.return_value = mock_openai_inst

    mock_claude_inst = AsyncMock()
    mock_claude_inst.chat = AsyncMock(side_effect=Exception("claude down"))
    mock_claude_cls.return_value = mock_claude_inst

    config = LLMConfig(
        openai=ProviderConfig(api_key="openai-key"),
        claude=ProviderConfig(api_key="claude-key"),
        auto_provider_preference=["openai", "claude"],
    )
    client = LLMClient(config)

    with pytest.raises(Exception, match="All providers failed"):
        await client.chat(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
@patch("backend.llm.client.ClaudeProvider")
@patch("backend.llm.client.OpenAIProvider")
async def test_chat_tracks_usage(mock_openai_cls, mock_claude_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_openai_inst.chat = AsyncMock(return_value=_mock_response("openai", "gpt-4o"))
    mock_openai_cls.return_value = mock_openai_inst

    mock_claude_inst = AsyncMock()
    mock_claude_cls.return_value = mock_claude_inst

    client = LLMClient(_make_config())
    await client.chat(
        messages=[{"role": "user", "content": "Hi"}],
        client_id="client-1",
        automation_id="auto-1",
        provider="openai",
    )

    assert len(client.tracker.records) == 1
    record = client.tracker.records[0]
    assert record.client_id == "client-1"
    assert record.automation_id == "auto-1"
    assert record.provider == "openai"


@pytest.mark.asyncio
@patch("backend.llm.client.OpenAIProvider")
async def test_embed_delegates_to_provider(mock_openai_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_response = MagicMock()
    mock_response.embedding = [0.1, 0.2]
    mock_response.model = "text-embedding-3-small"
    mock_response.provider = "openai"
    mock_response.tokens = 5
    mock_openai_inst.embed = AsyncMock(return_value=mock_response)
    mock_openai_cls.return_value = mock_openai_inst

    client = LLMClient(_make_config())
    await client.embed(text="hello", provider="openai")

    mock_openai_inst.embed.assert_called_once_with(text="hello", model=None)


@pytest.mark.asyncio
@patch("backend.llm.client.ClaudeProvider")
@patch("backend.llm.client.OpenAIProvider")
async def test_health_check_all_providers(mock_openai_cls, mock_claude_cls):
    from backend.llm.client import LLMClient

    mock_openai_inst = AsyncMock()
    mock_openai_inst.health_check = AsyncMock(return_value=True)
    mock_openai_cls.return_value = mock_openai_inst

    mock_claude_inst = AsyncMock()
    mock_claude_inst.health_check = AsyncMock(return_value=False)
    mock_claude_cls.return_value = mock_claude_inst

    client = LLMClient(_make_config())
    results = await client.health_check()

    assert results["openai"] is True
    assert results["claude"] is False


@pytest.mark.asyncio
@patch("backend.llm.client.OpenAIProvider")
async def test_resolve_provider_explicit(mock_openai_cls):
    from backend.llm.client import LLMClient

    mock_openai_cls.return_value = AsyncMock()
    client = LLMClient(_make_config())
    provider = client._resolve_provider("openai", None)
    assert provider == "openai"


@pytest.mark.asyncio
@patch("backend.llm.client.OpenAIProvider")
async def test_resolve_provider_auto_selects_first_available(
    mock_openai_cls,
):
    from backend.llm.client import LLMClient

    mock_openai_cls.return_value = AsyncMock()
    client = LLMClient(_make_config())
    provider = client._resolve_provider(None, None)
    assert provider == "openai"

"""Tests for LLM providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from backend.llm.providers.base import EmbeddingResponse, LLMResponse


def _mock_chat_response():
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content="Hello!"), finish_reason="stop")]
    resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    resp.model = "gpt-4o"
    return resp


def _mock_embedding_response():
    resp = MagicMock()
    resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    resp.model = "text-embedding-3-small"
    resp.usage = MagicMock(prompt_tokens=8)
    return resp


@pytest.mark.asyncio
@patch("backend.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_chat_returns_response(mock_async_openai):
    from backend.llm.providers.openai_provider import OpenAIProvider

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_chat_response())
    mock_async_openai.return_value = mock_client

    provider = OpenAIProvider(api_key="test-key")
    result = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello!"
    assert result.model == "gpt-4o"
    assert result.provider == "openai"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.total_tokens == 15
    assert result.finish_reason == "stop"
    assert isinstance(result.latency_ms, float)


@pytest.mark.asyncio
@patch("backend.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_health_check(mock_async_openai):
    from backend.llm.providers.openai_provider import OpenAIProvider

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_chat_response())
    mock_async_openai.return_value = mock_client

    provider = OpenAIProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is True


@pytest.mark.asyncio
@patch("backend.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_health_check_failure(mock_async_openai):
    from backend.llm.providers.openai_provider import OpenAIProvider

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("connection error"))
    mock_async_openai.return_value = mock_client

    provider = OpenAIProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is False


@pytest.mark.asyncio
@patch("backend.llm.providers.openai_provider.AsyncOpenAI")
async def test_openai_embed_returns_response(mock_async_openai):
    from backend.llm.providers.openai_provider import OpenAIProvider

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=_mock_embedding_response())
    mock_async_openai.return_value = mock_client

    provider = OpenAIProvider(api_key="test-key")
    result = await provider.embed(text="test text")

    assert isinstance(result, EmbeddingResponse)
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.model == "text-embedding-3-small"
    assert result.provider == "openai"
    assert result.tokens == 8


# --- Gemini ---


def _mock_gemini_chat_response():
    resp = MagicMock()
    resp.text = "Hello from Gemini!"
    resp.usage_metadata = MagicMock(
        prompt_token_count=10,
        candidates_token_count=5,
        total_token_count=15,
    )
    resp.candidates = [MagicMock(finish_reason=0)]
    return resp


def _mock_gemini_embed_response():
    resp = MagicMock()
    resp.embedding = MagicMock(values=[0.1, 0.2, 0.3])
    resp.total_token_count = 8
    return resp


@pytest.mark.asyncio
@patch("backend.llm.providers.gemini_provider.genai")
async def test_gemini_chat_returns_response(mock_genai):
    from backend.llm.providers.gemini_provider import GeminiProvider

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=_mock_gemini_chat_response())
    mock_genai.GenerativeModel.return_value = mock_model

    provider = GeminiProvider(api_key="test-key")
    result = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello from Gemini!"
    assert result.provider == "gemini"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.total_tokens == 15
    assert isinstance(result.latency_ms, float)


@pytest.mark.asyncio
@patch("backend.llm.providers.gemini_provider.genai")
async def test_gemini_health_check(mock_genai):
    from backend.llm.providers.gemini_provider import GeminiProvider

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=_mock_gemini_chat_response())
    mock_genai.GenerativeModel.return_value = mock_model

    provider = GeminiProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is True


@pytest.mark.asyncio
@patch("backend.llm.providers.gemini_provider.genai")
async def test_gemini_health_check_failure(mock_genai):
    from backend.llm.providers.gemini_provider import GeminiProvider

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(side_effect=Exception("API error"))
    mock_genai.GenerativeModel.return_value = mock_model

    provider = GeminiProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is False


@pytest.mark.asyncio
@patch("backend.llm.providers.gemini_provider.genai")
async def test_gemini_embed_returns_response(mock_genai):
    from backend.llm.providers.gemini_provider import GeminiProvider

    mock_genai.embed_content_async = AsyncMock(return_value=_mock_gemini_embed_response())

    provider = GeminiProvider(api_key="test-key")
    result = await provider.embed(text="test text")

    assert isinstance(result, EmbeddingResponse)
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.provider == "gemini"
    assert result.tokens == 8


def _mock_claude_chat_response():
    resp = MagicMock()
    resp.content = [TextBlock(type="text", text="Hello from Claude!")]
    resp.model = "claude-3-5-sonnet-20241022"
    resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    resp.stop_reason = "end_turn"
    return resp


@pytest.mark.asyncio
@patch("backend.llm.providers.claude_provider.AsyncAnthropic")
async def test_claude_chat_returns_response(mock_async_anthropic):
    from backend.llm.providers.claude_provider import ClaudeProvider

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=_mock_claude_chat_response())
    mock_async_anthropic.return_value = mock_client

    provider = ClaudeProvider(api_key="test-key")
    result = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

    assert isinstance(result, LLMResponse)
    assert result.content == "Hello from Claude!"
    assert result.model == "claude-3-5-sonnet-20241022"
    assert result.provider == "claude"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.total_tokens == 15
    assert result.finish_reason == "end_turn"
    assert isinstance(result.latency_ms, float)


@pytest.mark.asyncio
@patch("backend.llm.providers.claude_provider.AsyncAnthropic")
async def test_claude_health_check(mock_async_anthropic):
    from backend.llm.providers.claude_provider import ClaudeProvider

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=_mock_claude_chat_response())
    mock_async_anthropic.return_value = mock_client

    provider = ClaudeProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is True


@pytest.mark.asyncio
@patch("backend.llm.providers.claude_provider.AsyncAnthropic")
async def test_claude_health_check_failure(mock_async_anthropic):
    from backend.llm.providers.claude_provider import ClaudeProvider

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("connection error"))
    mock_async_anthropic.return_value = mock_client

    provider = ClaudeProvider(api_key="test-key")
    result = await provider.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_claude_embed_raises_not_implemented():
    from backend.llm.providers.claude_provider import ClaudeProvider

    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await provider.embed(text="test")

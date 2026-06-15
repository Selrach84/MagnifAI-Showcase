"""Tests for LLM API endpoints."""


async def test_chat_endpoint(client):
    """POST /api/llm/chat returns 200 with ChatResponse fields."""
    response = await client.post(
        "/api/llm/chat",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "provider": "openai",
            "model": "gpt-4o",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Mock response"
    assert data["model"] == "gpt-4o"
    assert data["provider"] == "openai"
    assert data["input_tokens"] == 10
    assert data["output_tokens"] == 20
    assert data["latency_ms"] == 100.0


async def test_chat_endpoint_defaults(client):
    """POST /api/llm/chat uses defaults when provider/model omitted."""
    response = await client.post(
        "/api/llm/chat",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-4o"
    assert data["provider"] == "openai"


async def test_list_providers(client):
    """GET /api/llm/providers returns provider list."""
    response = await client.get("/api/llm/providers")
    assert response.status_code == 200
    data = response.json()
    providers = data["providers"]
    assert len(providers) == 3
    names = [p["name"] for p in providers]
    assert "openai" in names
    assert "claude" in names
    assert "gemini" in names


async def test_llm_health(client):
    """GET /api/llm/health returns ok."""
    response = await client.get("/api/llm/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["providers"] == ["openai", "claude", "gemini"]

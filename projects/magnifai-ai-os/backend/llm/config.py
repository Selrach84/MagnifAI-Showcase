from pydantic import BaseModel


class ProviderConfig(BaseModel):
    api_key: str
    default_model: str = "gpt-4o"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 30.0


class LLMConfig(BaseModel):
    openai: ProviderConfig | None = None
    claude: ProviderConfig | None = None
    gemini: ProviderConfig | None = None
    auto_provider_preference: list[str] = ["openai", "claude", "gemini"]

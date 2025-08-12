from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    openai_api_key: SecretStr | None = None
    billing_adapter: str | None = None
    mcp_endpoint: str | None = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    stt_provider: str = "openai"
    stt_model: str = "whisper-1"
    telephony_provider: str = "twilio"
    tts_provider: str = "gtts"
    elevenlabs_api_key: SecretStr | None = None
    fail_on_llm_unavailable: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

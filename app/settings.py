import os
from dataclasses import dataclass

@dataclass
class Settings:
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    billing_adapter: str | None = os.getenv('BILLING_ADAPTER')
    mcp_endpoint: str | None = os.getenv('MCP_ENDPOINT')
    llm_provider: str = os.getenv('LLM_PROVIDER', 'openai')
    llm_model: str = os.getenv('LLM_MODEL', 'gpt-4o')
    ollama_base_url: str = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    stt_provider: str = os.getenv('STT_PROVIDER', 'openai')
    stt_model: str = os.getenv('STT_MODEL', 'whisper-1')
    telephony_provider: str = os.getenv('TELEPHONY_PROVIDER', 'twilio')
    tts_provider: str = os.getenv('TTS_PROVIDER', 'gtts')
    elevenlabs_api_key: str | None = os.getenv('ELEVENLABS_API_KEY')

settings = Settings()

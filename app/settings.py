import os
from dataclasses import dataclass

@dataclass
class Settings:
    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    billing_adapter: str | None = os.getenv('BILLING_ADAPTER')
    mcp_endpoint: str | None = os.getenv('MCP_ENDPOINT')

settings = Settings()

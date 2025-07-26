"""LLM-based invoice context extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
import requests
from openai import OpenAI

from app.settings import settings


class LLMProvider(ABC):
    """Abstract base class for LLM integrations."""

    @abstractmethod
    def extract(self, transcript: str) -> str:
        """Return JSON context extracted from the transcript."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """Use OpenAI chat completions API."""

    def extract(self, transcript: str) -> str:
        client = OpenAI()
        prompt = _build_prompt(transcript)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein strukturierter JSON-Extraktor für Handwerker.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    """Use a local Ollama server."""

    def extract(self, transcript: str) -> str:
        prompt = _build_prompt(transcript)
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        resp = requests.post(
            url,
            json={"model": settings.llm_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _build_prompt(transcript: str) -> str:
    return f"""Du bist ein KI-Assistent für Handwerker. Extrahiere aus folgendem Text eine strukturierte JSON-Rechnung gemäß folgendem Schema:

{{
  "type": "InvoiceContext",
  "customer": {{ "name": str }},
  "service": {{ "description": str, "materialIncluded": bool }},
  "amount": {{ "total": float, "currency": "EUR" }}
}}

Text: "{transcript}"
Nur JSON antworten."""


_LLM_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def _select_provider() -> LLMProvider:
    try:
        provider_cls = _LLM_PROVIDERS[settings.llm_provider]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported LLM_PROVIDER {settings.llm_provider}")
    return provider_cls()


def extract_invoice_context(transcript: str) -> str:
    """Extract structured invoice context from the transcript."""
    provider = _select_provider()
    return provider.extract(transcript)


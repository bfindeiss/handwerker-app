"""Kommunikation mit unterschiedlichen LLM-Anbietern."""

from __future__ import annotations

from abc import ABC, abstractmethod

import logging
import httpx
from fastapi import HTTPException
from openai import OpenAI

from app.settings import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstrakte Basis für alle Large-Language-Model-Backends."""

    @abstractmethod
    def extract(self, transcript: str) -> str:
        """Gibt aus einem Transkript extrahiertes JSON zurück."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """Verwendet die Chat-Completions-API von OpenAI."""

    def extract(self, transcript: str) -> str:
        client = OpenAI()
        prompt = _build_prompt(transcript)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein strukturierter JSON-Extraktor " "für Handwerker."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    """Spricht mit einem lokalen Ollama-Server."""

    def extract(self, transcript: str) -> str:
        prompt = _build_prompt(transcript)
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            resp = httpx.post(
                url,
                json={"model": settings.llm_model, "prompt": prompt, "stream": False},
                timeout=60,
            )
        except httpx.RequestError as exc:
            logger.exception("Failed to contact Ollama server at %s", url)
            raise HTTPException(
                status_code=503, detail="Ollama server unreachable"
            ) from exc
        if resp.status_code == 404:
            # Ollama returns 404 when the model is unknown or not pulled yet.
            # Surface a clearer error message so users know how to resolve it.
            try:
                detail = resp.json().get("error", "model not found")
            except Exception:  # pragma: no cover - invalid JSON
                detail = "model not found"
            logger.error(
                "Ollama model '%s' unavailable: %s", settings.llm_model, detail
            )
            raise RuntimeError(
                f"Ollama model '{settings.llm_model}' unavailable: {detail}"
            )

        resp.raise_for_status()
        logger.debug("Ollama response: %s", getattr(resp, "text", resp))
        return resp.json().get("response", "")


def _build_prompt(transcript: str) -> str:
    """Stellt den Eingabetext für das LLM zusammen."""
    return (
        "Du bist ein KI-Assistent für Handwerker. Extrahiere aus folgendem Text "
        "eine strukturierte JSON-Rechnung gemäß folgendem Schema:\n\n"
        "{\n"
        '  "type": "InvoiceContext",\n'
        '  "customer": { "name": str },\n'
        '  "service": { "description": str, "materialIncluded": bool },\n'
        '  "amount": { "total": float, "currency": "EUR" }\n'
        "}\n\n"
        f'Text: "{transcript}"\n'
        "Nur JSON antworten."
    )


_LLM_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def _select_provider() -> LLMProvider:
    """Gibt den konfigurierten LLM-Provider zurück."""
    try:
        provider_cls = _LLM_PROVIDERS[settings.llm_provider]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported LLM_PROVIDER {settings.llm_provider}")
    return provider_cls()


def extract_invoice_context(transcript: str) -> str:
    """Hauptschnittstelle für die restliche App."""
    provider = _select_provider()
    return provider.extract(transcript)


def check_llm_backend(timeout: float = 5.0) -> bool:
    """Prüft, ob das gewählte LLM erreichbar ist."""
    try:
        if settings.llm_provider == "openai":
            client = OpenAI()
            # Listing models is a lightweight way to verify connectivity.
            client.models.list()
        elif settings.llm_provider == "ollama":
            url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            httpx.get(url, timeout=timeout).raise_for_status()
        else:  # pragma: no cover - unrecognised provider
            return True
    except Exception:
        return False
    return True

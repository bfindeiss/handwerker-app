"""Kommunikation mit unterschiedlichen LLM-Anbietern."""

from __future__ import annotations

from abc import ABC, abstractmethod

import logging
import httpx
from fastapi import HTTPException
from openai import OpenAI
import json

from app.settings import settings
from app.logging_config import mask_pii
from app.models import (
    CustomerPass,
    ExtractionResult,
    LaborPass,
    MaterialPass,
    PreextractCandidates,
    TravelPass,
    extraction_result_json_schema,
    missing_extraction_fields,
    parse_model_json,
)
from app.preextract import preextract_candidates
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstrakte Basis für alle Large-Language-Model-Backends."""

    @abstractmethod
    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Gibt eine JSON-Ausgabe auf Basis des Prompts zurück."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """Verwendet die Chat-Completions-API von OpenAI."""

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        client = OpenAI()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
        )
        try:
            raw_response = response.model_dump_json()
        except AttributeError:  # Dummy objects in tests may not provide this
            raw_response = str(response)
        logger.debug("OpenAI full response: %s", mask_pii(raw_response))
        reasoning = getattr(response.choices[0].message, "reasoning", None)
        if reasoning:
            logger.debug("OpenAI reasoning: %s", mask_pii(reasoning))
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    """Spricht mit einem lokalen Ollama-Server."""

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        timeout_s = max(300.0, settings.ollama_timeout)
        try:
            resp = httpx.post(
                url,
                json={
                    "model": settings.llm_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=httpx.Timeout(timeout_s, connect=5.0),
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
        resp_json = resp.json()
        logger.debug("Ollama full response: %s", mask_pii(str(resp_json)))
        return resp_json.get("response", "")


SYSTEM_PROMPT = (
    "Du bist ein strukturierter JSON-Reconciler für Handwerker. "
    "Nutze die Kandidatenliste als primäre Quelle und den Text nur zum Abgleich. "
    "Keine Erfindungen: Wenn etwas nicht im Text steht, verwende null oder leere Listen. "
    "Geldwerte immer als Cent-Integer, Stunden als float, Kilometer als float. "
    "Füge Unsicherheiten in die notes-Liste ein. "
    "Antworte ausschließlich mit JSON gemäß dem Schema. "
    "Gib niemals das Schema selbst aus (kein $defs, keine properties, keine $schema)."
)


def _schema_to_text(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False)


def _build_prompt(transcript: str, candidates: PreextractCandidates) -> str:
    """Stellt den Eingabetext für das LLM zusammen."""
    schema = _schema_to_text(extraction_result_json_schema())
    candidates_json = candidates.model_dump_json()
    prompt = (
        "Du bist ein Reconciler: Nutze den Originaltext nur zum Abgleich, "
        "nicht als primäre Quelle. Verwende die Kandidatenliste als Basis "
        "für die ExtractionResult-Struktur.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Text:\n{transcript}\n\n"
        f"Kandidaten (JSON):\n{candidates_json}\n"
        "Antworte ausschließlich mit gültigem JSON entsprechend dem Schema."
    )
    logger.debug("LLM prompt: %s", mask_pii(prompt))
    return prompt


def _build_pass_prompt(
    transcript: str,
    candidates: PreextractCandidates,
    task: str,
    schema: dict,
) -> str:
    schema_text = _schema_to_text(schema)
    candidates_json = candidates.model_dump_json()
    prompt = (
        f"{task}\n\n"
        f"Schema:\n{schema_text}\n\n"
        f"Text:\n{transcript}\n\n"
        f"Kandidaten (JSON):\n{candidates_json}\n"
        "Antworte ausschließlich mit gültigem JSON entsprechend dem Schema."
    )
    logger.debug("LLM pass prompt: %s", mask_pii(prompt))
    return prompt


def _build_repair_prompt(
    task: str,
    schema: dict,
    raw_response: str,
    candidates: PreextractCandidates,
    transcript: str,
) -> str:
    schema_text = _schema_to_text(schema)
    candidates_json = candidates.model_dump_json()
    prompt = (
        f"{task}\n\n"
        "Die vorherige Antwort war ungültiges JSON oder entsprach nicht dem Schema. "
        "Gib gültiges JSON gemäß dem Schema zurück.\n\n"
        f"Schema:\n{schema_text}\n\n"
        f"Text:\n{transcript}\n\n"
        f"Kandidaten (JSON):\n{candidates_json}\n\n"
        f"Ungültige Antwort:\n{raw_response}\n"
        "Antworte ausschließlich mit gültigem JSON entsprechend dem Schema."
    )
    logger.debug("LLM repair prompt: %s", mask_pii(prompt))
    return prompt


def _run_pass(
    provider: LLMProvider,
    transcript: str,
    candidates: PreextractCandidates,
    task: str,
    model_cls: type,
) -> BaseModel:
    schema = model_cls.model_json_schema()
    prompt = _build_pass_prompt(transcript, candidates, task, schema)
    response = provider.complete(prompt, system_prompt=SYSTEM_PROMPT)
    try:
        return parse_model_json(response, model_cls, error_label="invalid pass payload")
    except ValueError:
        repair_prompt = _build_repair_prompt(
            task,
            schema,
            response,
            candidates,
            transcript,
        )
        repair_response = provider.complete(repair_prompt, system_prompt=SYSTEM_PROMPT)
        return parse_model_json(
            repair_response, model_cls, error_label="invalid pass payload"
        )


def _merge_passes(
    customer_pass: CustomerPass,
    material_pass: MaterialPass,
    labor_pass: LaborPass,
    travel_pass: TravelPass,
) -> ExtractionResult:
    line_items = (
        material_pass.line_items + labor_pass.line_items + travel_pass.line_items
    )
    notes = (
        customer_pass.notes
        + material_pass.notes
        + labor_pass.notes
        + travel_pass.notes
    )
    return ExtractionResult(
        customer=customer_pass.customer,
        line_items=line_items,
        notes=notes,
    )


def _extract_multi_pass(
    provider: LLMProvider,
    transcript: str,
    candidates: PreextractCandidates,
) -> str:
    customer_pass = _run_pass(
        provider,
        transcript,
        candidates,
        task="Pass 1: Extrahiere Kunde und Adresse.",
        model_cls=CustomerPass,
    )
    material_pass = _run_pass(
        provider,
        transcript,
        candidates,
        task="Pass 2: Extrahiere alle Materialpositionen.",
        model_cls=MaterialPass,
    )
    labor_pass = _run_pass(
        provider,
        transcript,
        candidates,
        task="Pass 3: Extrahiere Arbeitszeiten inklusive Rolle (meister/geselle).",
        model_cls=LaborPass,
    )
    travel_pass = _run_pass(
        provider,
        transcript,
        candidates,
        task="Pass 4: Extrahiere Fahrtkosten und sonstige Positionen als travel.",
        model_cls=TravelPass,
    )
    merged = _merge_passes(customer_pass, material_pass, labor_pass, travel_pass)
    missing = missing_extraction_fields(merged)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    return merged.model_dump_json()


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
    candidates = preextract_candidates(transcript)
    return _extract_multi_pass(provider, transcript, candidates)


def check_llm_backend(timeout: float = 5.0) -> bool:
    """Prüft, ob das gewählte LLM erreichbar ist."""
    try:
        if settings.llm_provider == "openai":
            client = OpenAI()
            # Listing models is a lightweight way to verify connectivity.
            client.models.list()
        elif settings.llm_provider == "ollama":
            url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            httpx.get(
                url, timeout=httpx.Timeout(timeout, connect=5.0)
            ).raise_for_status()
        else:  # pragma: no cover - unrecognised provider
            return True
    except Exception:
        return False
    return True

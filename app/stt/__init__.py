"""Speech-to-text provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shlex
import subprocess  # nosec B404
import tempfile
from typing import Any

import yaml  # type: ignore

from openai import OpenAI

from app.settings import settings


class STTProvider(ABC):
    """Basisklasse für alle Speech-to-Text-Backends."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        """Wandelt rohe Audio-Bytes in Text um."""
        raise NotImplementedError


class OpenAITranscriber(STTProvider):
    """Nutzen die Whisper-API von OpenAI."""

    def transcribe(self, audio_bytes: bytes) -> str:
        client = OpenAI()
        response = client.audio.transcriptions.create(
            model=settings.stt_model,
            file=BytesIO(audio_bytes),
            response_format="text",
            prompt=settings.stt_prompt,
            language=settings.stt_language,
        )
        return response.text if hasattr(response, "text") else str(response)


class CommandTranscriber(STTProvider):
    """Startet ein lokales Kommandozeilen-Tool."""

    def transcribe(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            command = shlex.split(settings.stt_model)
            for token in command:
                if token in {";", "&", "|", "&&", "||", "`", "$", ">", "<"}:
                    raise ValueError("Unsafe token in stt_model")
            result = subprocess.run(  # nosec B603
                command + ["--language", settings.stt_language, tmp.name],
                capture_output=True,
                text=True,
                check=True,
            )
        os.unlink(tmp.name)
        return result.stdout.strip()


class WhisperTranscriber(STTProvider):
    """Verwendet das lokale `whisper`-Paket."""

    _model_cache: dict[str, Any] = {}

    def __init__(self) -> None:
        # Lazy import to avoid mandatory dependency during test runs
        import whisper  # type: ignore

        try:
            import numpy  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment issue
            raise RuntimeError(
                "WhisperTranscriber requires NumPy. Install it with "
                "'pip install numpy' or set STT_PROVIDER=openai."
            ) from exc

        import shutil

        if shutil.which("ffmpeg") is None:  # pragma: no cover - environment issue
            raise RuntimeError(
                "WhisperTranscriber requires ffmpeg. Install it and try again "
                "or set STT_PROVIDER=openai."
            )

        if settings.stt_model not in self._model_cache:
            try:
                self._model_cache[settings.stt_model] = whisper.load_model(
                    settings.stt_model
                )
            except RuntimeError as exc:  # pragma: no cover - environment issue
                if "Numpy is not available" in str(exc):
                    raise RuntimeError(
                        "WhisperTranscriber requires NumPy. Install it with "
                        "'pip install numpy' or set STT_PROVIDER=openai."
                    ) from exc
                raise
        self.model = self._model_cache[settings.stt_model]

    def transcribe(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            result = self.model.transcribe(tmp.name, language=settings.stt_language)
        os.unlink(tmp.name)
        return result.get("text", "").strip()


_STT_PROVIDERS: dict[str, type[STTProvider]] = {
    "openai": OpenAITranscriber,
    "command": CommandTranscriber,
    "whisper": WhisperTranscriber,
}


def _select_provider() -> STTProvider:
    """Wählt anhand der Einstellung den passenden Provider aus."""
    provider_name = settings.stt_provider
    try:
        provider_cls = _STT_PROVIDERS[provider_name]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported STT_PROVIDER {settings.stt_provider}")
    return provider_cls()


def transcribe_audio(audio_bytes: bytes) -> str:
    """Convenience-Funktion für andere Module."""
    provider = _select_provider()
    raw = provider.transcribe(audio_bytes)
    return _normalize_transcript(raw)


def _load_transcript_replacements() -> dict[str, str]:
    """Liest optionale Ersetzungstabellen aus JSON oder YAML."""
    base = Path(__file__).with_name("transcript_replacements")
    loaders = {
        ".json": json.load,
        ".yaml": yaml.safe_load,
        ".yml": yaml.safe_load,
    }
    for suffix, loader in loaders.items():
        path = base.with_suffix(suffix)
        if path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                data = loader(handle) or {}
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            return {}
    return {}


_TRANSCRIPT_REPLACEMENTS = _load_transcript_replacements()


_NUMBER_WORDS = {
    "null": "0",
    "eins": "1",
    "ein": "1",
    "eine": "1",
    "einen": "1",
    "zwei": "2",
    "drei": "3",
    "vier": "4",
    "fünf": "5",
    "fuenf": "5",
    "sechs": "6",
    "sieben": "7",
    "acht": "8",
    "neun": "9",
    "zehn": "10",
    "elf": "11",
    "zwölf": "12",
    "zwoelf": "12",
    "dreizehn": "13",
    "vierzehn": "14",
    "fünfzehn": "15",
    "funfzehn": "15",
    "sechzehn": "16",
    "siebzehn": "17",
    "achtzehn": "18",
    "neunzehn": "19",
    "zwanzig": "20",
    "dreißig": "30",
    "dreissig": "30",
    "vierzig": "40",
    "fünfzig": "50",
    "funfzig": "50",
    "sechzig": "60",
    "siebzig": "70",
    "achtzig": "80",
    "neunzig": "90",
    "hundert": "100",
}


def _replace_number_words(text: str) -> str:
    pattern = r"\b(" + "|".join(re.escape(w) for w in _NUMBER_WORDS.keys()) + r")\b"

    def repl(match: re.Match[str]) -> str:
        return _NUMBER_WORDS[match.group(0).lower()]

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _normalize_transcript(text: str) -> str:
    """Korrigiert häufige Erkennungsfehler im Transkript."""
    for wrong, correct in _TRANSCRIPT_REPLACEMENTS.items():
        text = text.replace(wrong, correct)
    return _replace_number_words(text)

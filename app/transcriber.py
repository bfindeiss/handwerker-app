"""Speech-to-text provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import os
import shlex
import subprocess
import tempfile
from typing import Any

from openai import OpenAI

from app.settings import settings


class STTProvider(ABC):
    """Abstract base class for speech-to-text backends."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        """Convert raw audio bytes to text."""
        raise NotImplementedError


class OpenAITranscriber(STTProvider):
    """Use OpenAI Whisper API for transcription."""

    def transcribe(self, audio_bytes: bytes) -> str:
        client = OpenAI()
        response = client.audio.transcriptions.create(
            model=settings.stt_model,
            file=BytesIO(audio_bytes),
            response_format="text",
        )
        return response.text if hasattr(response, "text") else str(response)


class CommandTranscriber(STTProvider):
    """Run a local command line tool for transcription."""

    def transcribe(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            result = subprocess.run(
                shlex.split(settings.stt_model) + [tmp.name],
                capture_output=True,
                text=True,
                check=True,
            )
        os.unlink(tmp.name)
        return result.stdout.strip()


class WhisperTranscriber(STTProvider):
    """Use the local whisper package for transcription."""

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
            result = self.model.transcribe(tmp.name)
        os.unlink(tmp.name)
        return result.get("text", "").strip()


_STT_PROVIDERS: dict[str, type[STTProvider]] = {
    "openai": OpenAITranscriber,
    "command": CommandTranscriber,
    "whisper": WhisperTranscriber,
}


def _select_provider() -> STTProvider:
    """Return the configured speech-to-text provider."""
    provider_name = settings.stt_provider
    try:
        provider_cls = _STT_PROVIDERS[provider_name]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported STT_PROVIDER {settings.stt_provider}")
    return provider_cls()


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using the configured provider."""
    provider = _select_provider()
    return provider.transcribe(audio_bytes)

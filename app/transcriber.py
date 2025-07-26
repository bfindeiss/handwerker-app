"""Speech-to-text provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import os
import shlex
import subprocess
import tempfile
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


_STT_PROVIDERS: dict[str, type[STTProvider]] = {
    "openai": OpenAITranscriber,
    "command": CommandTranscriber,
}


def _select_provider() -> STTProvider:
    try:
        provider_cls = _STT_PROVIDERS[settings.stt_provider]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported STT_PROVIDER {settings.stt_provider}")
    return provider_cls()


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio using the configured provider."""
    provider = _select_provider()
    return provider.transcribe(audio_bytes)


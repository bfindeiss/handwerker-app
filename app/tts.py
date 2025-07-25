"""Text-to-speech provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from gtts import gTTS


class TTSProvider(ABC):
    """Abstract base class for TTS backends."""

    @abstractmethod
    def synthesize(self, text: str, lang: str = "de") -> bytes:
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    """Use gTTS to generate speech."""

    def synthesize(self, text: str, lang: str = "de") -> bytes:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()


def _select_provider() -> TTSProvider:
    return GTTSProvider()


def text_to_speech(text: str, lang: str = "de") -> bytes:
    """Generate speech using the configured provider."""
    provider = _select_provider()
    return provider.synthesize(text, lang)

"""Text-to-speech provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from gtts import gTTS
from elevenlabs.client import ElevenLabs

from app.settings import settings


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


class ElevenLabsProvider(TTSProvider):
    """Use ElevenLabs API to generate speech."""

    def synthesize(self, text: str, lang: str = "de") -> bytes:
        if not settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        audio_iter = client.text_to_speech.convert(
            voice_id="Mats",
            text=text,
            model_id="eleven_monolingual_v1",
            language_code=lang,
            output_format="mp3_44100_128",
        )
        return b"".join(audio_iter)


def _select_provider() -> TTSProvider:
    if settings.tts_provider == "gtts":
        return GTTSProvider()
    if settings.tts_provider == "elevenlabs":
        return ElevenLabsProvider()
    raise ValueError(f"Unsupported TTS_PROVIDER {settings.tts_provider}")


def text_to_speech(text: str, lang: str = "de") -> bytes:
    """Generate speech using the configured provider."""
    provider = _select_provider()
    return provider.synthesize(text, lang)

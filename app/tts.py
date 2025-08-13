"""Text-to-speech provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from gtts import gTTS
from elevenlabs.client import ElevenLabs

from app.settings import settings


class TTSProvider(ABC):
    """Abstrakte Basis für verschiedene Text-zu-Sprache-Anbieter."""

    @abstractmethod
    def synthesize(self, text: str, lang: str = "de") -> bytes:
        """Erzeugt Audiobits aus Text."""
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    """Verwendet das freie `gTTS`-Paket."""

    def synthesize(self, text: str, lang: str = "de") -> bytes:
        tts = gTTS(text=text, lang=lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()


class ElevenLabsProvider(TTSProvider):
    """Bindet den Cloud-Dienst von ElevenLabs ein."""

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


_TTS_PROVIDERS: dict[str, type[TTSProvider]] = {
    "gtts": GTTSProvider,
    "elevenlabs": ElevenLabsProvider,
}


def _select_provider() -> TTSProvider:
    """Ermittelt anhand der Einstellungen die zu nutzende Implementierung."""
    try:
        provider_cls = _TTS_PROVIDERS[settings.tts_provider]
    except KeyError:  # pragma: no cover - configuration error
        raise ValueError(f"Unsupported TTS_PROVIDER {settings.tts_provider}")
    return provider_cls()


def text_to_speech(text: str, lang: str = "de") -> bytes:
    """Hilfsfunktion für den Rest der App."""
    provider = _select_provider()
    return provider.synthesize(text, lang)

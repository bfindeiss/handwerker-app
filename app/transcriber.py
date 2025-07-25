from io import BytesIO
import tempfile
import os
import shlex
import subprocess
from openai import OpenAI
from app.settings import settings


def transcribe_audio(audio_bytes: bytes) -> str:
    if settings.stt_provider == "openai":
        client = OpenAI()
        response = client.audio.transcriptions.create(
            model=settings.stt_model,
            file=BytesIO(audio_bytes),
            response_format="text",
        )
        return response.text if hasattr(response, "text") else str(response)
    elif settings.stt_provider == "command":
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
    else:
        raise ValueError(f"Unsupported STT_PROVIDER {settings.stt_provider}")


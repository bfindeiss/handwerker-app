from io import BytesIO
from openai import OpenAI


def transcribe_audio(audio_bytes: bytes) -> str:
    client = OpenAI()
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=BytesIO(audio_bytes),
        response_format="text",
    )
    return response.text if hasattr(response, "text") else str(response)


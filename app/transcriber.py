def transcribe_audio(audio_bytes: bytes) -> str:
    from openai import OpenAI
    client = OpenAI()
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_bytes,
        response_format="text"
    )
    return response
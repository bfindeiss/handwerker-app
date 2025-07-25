from io import BytesIO
from gtts import gTTS


def text_to_speech(text: str, lang: str = "de") -> bytes:
    tts = gTTS(text=text, lang=lang)
    fp = BytesIO()
    tts.write_to_fp(fp)
    return fp.getvalue()

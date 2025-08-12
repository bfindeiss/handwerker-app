from pathlib import Path

import httpx
from fastapi import BackgroundTasks

from app.billing_adapter import send_to_billing_system
from app.models import InvoiceContext
from app.persistence import store_interaction
from app.tts import text_to_speech

RECORDINGS_DIR = Path("recordings")
RECORDINGS_DIR.mkdir(exist_ok=True)


async def download_recording(url: str) -> bytes:
    """Download an audio recording from the given URL."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content


def finalize(
    audio_bytes: bytes,
    transcript: str,
    invoice: InvoiceContext,
    background_tasks: BackgroundTasks,
) -> None:
    """Send invoice to billing system and persist artefacts."""
    send_to_billing_system(invoice)
    log_dir = store_interaction(audio_bytes, transcript, invoice)

    def tts_and_store() -> None:
        speech_bytes = text_to_speech(
            "Die Rechnung für "
            f"{invoice.customer['name']} über {invoice.amount['total']} Euro "
            "wurde erstellt."
        )
        tts_path = RECORDINGS_DIR / f"{Path(log_dir).name}.mp3"
        tts_path.write_bytes(speech_bytes)

    background_tasks.add_task(tts_and_store)

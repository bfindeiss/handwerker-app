from fastapi import APIRouter, BackgroundTasks, Request

from app.llm_agent import extract_invoice_context
from app.models import missing_invoice_fields, parse_invoice_context
from app.stt import transcribe_audio

from .common import download_recording, finalize

router = APIRouter()


@router.post("/sipgate/voice")
def sipgate_voice(request: Request):
    """Erster Webhook: Gibt an Sipgate die URL für die Aufnahme zurück."""
    return {"record": str(request.url_for("sipgate_recording"))}


@router.post("/sipgate/recording")
async def sipgate_recording(request: Request, background_tasks: BackgroundTasks):
    """Wird nach dem Auflegen aufgerufen und verarbeitet die Aufnahme."""
    form = await request.form()
    recording_url = form.get("recordingUrl")
    if not recording_url:
        return {"error": "Keine Aufnahme erhalten."}
    audio_bytes = await download_recording(recording_url)
    transcript = transcribe_audio(audio_bytes)
    try:
        invoice_json = extract_invoice_context(transcript)
        invoice = parse_invoice_context(invoice_json)
    except ValueError:
        return {"error": "Ungültiger Rechnungsinhalt"}
    if missing_invoice_fields(invoice):
        return {"error": "Unvollständige Rechnungsdaten"}
    finalize(audio_bytes, transcript, invoice, background_tasks)
    return {"status": "ok"}

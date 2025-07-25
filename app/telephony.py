from pathlib import Path
from fastapi import APIRouter, Request, BackgroundTasks, Response
import requests
import json
from app.transcriber import transcribe_audio
from app.llm_agent import extract_invoice_context
from app.billing_adapter import send_to_billing_system
from app.persistence import store_interaction
from app.models import InvoiceContext
from app.tts import text_to_speech
from app.settings import settings

router = APIRouter()

RECORDINGS_DIR = Path("recordings")
RECORDINGS_DIR.mkdir(exist_ok=True)


def download_recording(url: str) -> bytes:
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content


def _handle_recording(audio_bytes: bytes, background_tasks: BackgroundTasks) -> None:
    transcript = transcribe_audio(audio_bytes)
    invoice_json = extract_invoice_context(transcript)
    invoice = InvoiceContext(**json.loads(invoice_json))
    send_to_billing_system(invoice)
    log_dir = store_interaction(audio_bytes, transcript, invoice)

    def tts_and_store():
        speech_bytes = text_to_speech(
            f"Die Rechnung für {invoice.customer['name']} über {invoice.amount['total']} Euro wurde erstellt."
        )
        tts_path = RECORDINGS_DIR / f"{Path(log_dir).name}.mp3"
        tts_path.write_bytes(speech_bytes)

    background_tasks.add_task(tts_and_store)


if settings.telephony_provider == "sipgate":

    @router.post("/sipgate/voice")
    def sipgate_voice(request: Request):
        """Initial Sipgate webhook to start recording."""
        return {"record": str(request.url_for("sipgate_recording"))}

    @router.post("/sipgate/recording")
    async def sipgate_recording(request: Request, background_tasks: BackgroundTasks):
        """Handle recording callback from Sipgate."""
        form = await request.form()
        recording_url = form.get("recordingUrl")
        if not recording_url:
            return {"error": "Keine Aufnahme erhalten."}
        audio_bytes = download_recording(recording_url)
        _handle_recording(audio_bytes, background_tasks)
        return {"status": "ok"}

else:
    from twilio.twiml.voice_response import VoiceResponse

    @router.post("/twilio/voice")
    def twilio_voice(request: Request):
        """Initial Twilio webhook to start recording."""
        vr = VoiceResponse()
        vr.say(
            "Bitte sprechen Sie nach dem Signal. Drücken Sie die Raute, wenn Sie fertig sind.",
            language="de-DE",
        )
        vr.record(
            max_length=60,
            action=str(request.url_for("twilio_recording")),
            play_beep=True,
            finish_on_key="#",
        )
        return Response(content=str(vr), media_type="application/xml")

    @router.post("/twilio/recording")
    async def twilio_recording(request: Request, background_tasks: BackgroundTasks):
        """Handle recording callback from Twilio."""
        form = await request.form()
        recording_url = form.get("RecordingUrl")
        if not recording_url:
            vr = VoiceResponse()
            vr.say("Keine Aufnahme erhalten.", language="de-DE")
            return Response(content=str(vr), media_type="application/xml")

        audio_bytes = download_recording(recording_url + ".wav")
        _handle_recording(audio_bytes, background_tasks)
        vr = VoiceResponse()
        vr.say("Vielen Dank. Ihre Rechnung wurde erstellt.", language="de-DE")
        return Response(content=str(vr), media_type="application/xml")

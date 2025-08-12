from fastapi import APIRouter, BackgroundTasks, Request, Response
from twilio.twiml.voice_response import VoiceResponse

from app.llm_agent import extract_invoice_context
from app.models import missing_invoice_fields, parse_invoice_context
from app.transcriber import transcribe_audio

from .common import download_recording, finalize

router = APIRouter()

# In-memory sessions to accumulate transcripts for follow-up questions.
SESSIONS: dict[str, str] = {}


@router.post("/twilio/voice")
def twilio_voice(request: Request):
    """Initial Twilio webhook to start recording."""
    vr = VoiceResponse()
    vr.say(
        "Bitte sprechen Sie nach dem Signal. "
        "Drücken Sie die Raute, wenn Sie fertig sind.",
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
    """Handle recording callback from Twilio with follow-up questions."""
    form = await request.form()
    recording_url = form.get("RecordingUrl")
    call_sid = form.get("CallSid")
    if not recording_url or not call_sid:
        vr = VoiceResponse()
        vr.say("Keine Aufnahme erhalten.", language="de-DE")
        return Response(content=str(vr), media_type="application/xml")

    audio_bytes = await download_recording(recording_url + ".wav")
    transcript_part = transcribe_audio(audio_bytes)
    full_transcript = (SESSIONS.get(call_sid, "") + " " + transcript_part).strip()
    SESSIONS[call_sid] = full_transcript

    invoice_json = extract_invoice_context(full_transcript)
    try:
        invoice = parse_invoice_context(invoice_json)
    except ValueError:
        missing = [
            "Bitte nennen Sie den Kundennamen, die Dienstleistung und den Betrag."
        ]
    else:
        missing = missing_invoice_fields(invoice)

    if missing:
        question_map = {
            "customer.name": "Wie heißt der Kunde?",
            "service.description": "Welche Dienstleistung wurde erbracht?",
            "amount.total": "Wie hoch ist der Gesamtbetrag?",
        }
        question = question_map.get(missing[0], missing[0])
        vr = VoiceResponse()
        vr.say(question, language="de-DE")
        vr.record(
            max_length=60,
            action=str(request.url_for("twilio_recording")),
            play_beep=True,
            finish_on_key="#",
        )
        return Response(content=str(vr), media_type="application/xml")

    finalize(audio_bytes, full_transcript, invoice, background_tasks)
    del SESSIONS[call_sid]
    vr = VoiceResponse()
    vr.say("Vielen Dank. Ihre Rechnung wurde erstellt.", language="de-DE")
    return Response(content=str(vr), media_type="application/xml")

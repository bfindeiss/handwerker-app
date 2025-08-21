from fastapi import APIRouter, BackgroundTasks, Request, Response
from twilio.twiml.voice_response import VoiceResponse

from app.llm_agent import extract_invoice_context
from app.models import missing_invoice_fields, parse_invoice_context
from app.stt import transcribe_audio

from .common import download_recording, finalize

router = APIRouter()

# Zwischenspeicher für laufende Anrufe. Twilio ruft mehrmals an und wir
# sammeln die Antworten hier pro Call SID.
SESSIONS: dict[str, str] = {}


@router.post("/twilio/voice")
def twilio_voice(request: Request):
    """Erster Webhook: begrüßt den Anrufer und startet die Aufzeichnung."""
    vr = VoiceResponse()
    vr.say(
        "Bitte sprechen Sie nach dem Signal. "
        "Drücken Sie die Raute, wenn Sie fertig sind.",
        language="de-DE",
    )
    # Twilio zeichnet bis zum Raute-Zeichen auf und ruft anschließend
    # ``twilio_recording`` auf.
    vr.record(
        max_length=60,
        action=str(request.url_for("twilio_recording")),
        play_beep=True,
        finish_on_key="#",
    )
    return Response(content=str(vr), media_type="application/xml")


@router.post("/twilio/recording")
async def twilio_recording(request: Request, background_tasks: BackgroundTasks):
    """Wird nach jeder Aufnahme aufgerufen und stellt ggf. Rückfragen."""
    form = await request.form()
    recording_url = form.get("RecordingUrl")
    call_sid = form.get("CallSid")
    if not recording_url or not call_sid:
        vr = VoiceResponse()
        vr.say("Keine Aufnahme erhalten.", language="de-DE")
        return Response(content=str(vr), media_type="application/xml")

    # Aufnahme herunterladen und an vorherige Teiltranskripte anhängen.
    audio_bytes = await download_recording(recording_url + ".wav")
    transcript_part = transcribe_audio(audio_bytes)
    full_transcript = (SESSIONS.get(call_sid, "") + " " + transcript_part).strip()
    SESSIONS[call_sid] = full_transcript

    # Kontext aus dem Transkript extrahieren und prüfen, ob Daten fehlen.
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
        # Wenn noch Pflichtfelder fehlen, gezielt nachfragen.
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

    # Alle Daten vorhanden → Rechnung speichern und aufräumen.
    finalize(audio_bytes, full_transcript, invoice, background_tasks)
    del SESSIONS[call_sid]
    vr = VoiceResponse()
    vr.say("Vielen Dank. Ihre Rechnung wurde erstellt.", language="de-DE")
    return Response(content=str(vr), media_type="application/xml")

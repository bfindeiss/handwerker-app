from __future__ import annotations

import base64
from typing import Dict

from fastapi import APIRouter, UploadFile, File, Form

from app.transcriber import transcribe_audio
from app.llm_agent import extract_invoice_context
from app.models import parse_invoice_context, missing_invoice_fields
from app.pricing import apply_pricing
from app.service_estimations import estimate_labor_item
from app.tts import text_to_speech
from app.billing_adapter import send_to_billing_system
from app.persistence import store_interaction

router = APIRouter()

# Zwischenspeicher für laufende Konversationen.
SESSIONS: Dict[str, str] = {}


@router.post("/conversation/")
async def voice_conversation(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Führt eine dialogorientierte Aufnahme durch."""
    audio_bytes = await file.read()

    # Neues Transkript zur Session hinzufügen.
    transcript_part = transcribe_audio(audio_bytes)
    full_transcript = (SESSIONS.get(session_id, "") + " " + transcript_part).strip()
    SESSIONS[session_id] = full_transcript

    # Rechnungsdaten aus dem bisherigen Gespräch extrahieren.
    invoice_json = extract_invoice_context(full_transcript)
    try:
        invoice = parse_invoice_context(invoice_json)
    except ValueError:
        # Wenn der KI-Auszug nicht geparst werden kann, starten wir die
        # Sitzung neu und bitten um eine Wiederholung. So verhindern wir,
        # dass sich missverstandene Ausschnitte anhäufen und immer wieder
        # dieselbe Nachfrage gestellt wird.
        SESSIONS.pop(session_id, None)
        question = (
            "Entschuldigung, ich konnte die Angaben nicht verstehen. "
            "Bitte nenne noch einmal Kundennamen, Dienstleistung und Betrag."
        )
        audio_b64 = base64.b64encode(text_to_speech(question)).decode("ascii")
        return {
            "done": False,
            "question": question,
            "audio": audio_b64,
            "transcript": full_transcript,
        }
    else:
        if not any(i.category == "labor" for i in invoice.items):
            invoice.items.append(
                estimate_labor_item(invoice.service.get("description", ""))
            )
        apply_pricing(invoice)
        missing = missing_invoice_fields(invoice)

    if missing:
        question_map = {
            "customer.name": "Wie heißt der Kunde?",
            "service.description": "Welche Dienstleistung wurde erbracht?",
            "amount.total": "Wie hoch ist der Gesamtbetrag?",
        }
        question = question_map.get(missing[0], missing[0])
        audio_b64 = base64.b64encode(text_to_speech(question)).decode("ascii")
        return {
            "done": False,
            "question": question,
            "audio": audio_b64,
            "transcript": full_transcript,
        }

    # Alle Angaben vollständig – Rechnung erzeugen und Session aufräumen.
    send_to_billing_system(invoice)
    log_dir = store_interaction(audio_bytes, full_transcript, invoice)
    SESSIONS.pop(session_id, None)
    message = (
        "Die Rechnung für "
        f"{invoice.customer['name']} über {invoice.amount['total']} Euro "
        "wurde erstellt."
    )
    audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
    return {
        "done": True,
        "message": message,
        "audio": audio_b64,
        "invoice": invoice.model_dump(mode="json"),
        "log_dir": log_dir,
        "transcript": full_transcript,
    }

"""Dialogbasierte Erfassung von Rechnungsdaten."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, File, Form, UploadFile

from app.billing_adapter import send_to_billing_system
from app.llm_agent import extract_invoice_context
from app.models import (
    InvoiceContext,
    missing_invoice_fields,
    parse_invoice_context,
)
from app.persistence import store_interaction
from app.pricing import apply_pricing
from app.service_estimations import estimate_labor_item
from app.transcriber import transcribe_audio
from app.tts import text_to_speech

router = APIRouter()

# Zwischenspeicher für laufende Konversationen
SESSIONS: Dict[str, str] = {}
# Zuletzt erfolgreicher Rechnungszustand pro Session
INVOICE_STATE: Dict[str, InvoiceContext] = {}

# Pfad zur Konfigurationsdatei
ENV_PATH = Path(".env")


def _save_env_value(key: str, value: str) -> None:
    """Persistiert einen Schlüssel-Wert-Paar in ``.env``."""

    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    prefix = f"{key}="
    replaced = False
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = f'{prefix}"{value}"'
            replaced = True
            break

    if not replaced:
        lines.append(f'{prefix}"{value}"')

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fill_default_fields(invoice: InvoiceContext) -> None:
    """Ergänzt fehlende Pflichtfelder durch Platzhalter."""

    if not invoice.customer.get("name"):
        invoice.customer["name"] = "Unbekannter Kunde"
    if not invoice.service.get("description"):
        invoice.service["description"] = "Dienstleistung nicht näher beschrieben"


@router.post("/conversation/")
async def voice_conversation(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Führt eine dialogorientierte Aufnahme durch."""

    audio_bytes = await file.read()
    transcript_part = transcribe_audio(audio_bytes)

    # Prüft auf Konfigurationsbefehle wie "Speichere meinen Firmennamen".
    m = re.search(
        r"speichere meinen firmennamen(?: (?P<name>.+))?",
        transcript_part,
        re.IGNORECASE,
    )
    if m:
        company = (m.group("name") or "").strip()
        if company:
            _save_env_value("COMPANY_NAME", company)
            message = f"Firmenname {company} gespeichert."
        else:
            message = "Kein Firmenname erkannt."
        audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
        return {
            "done": False,
            "message": message,
            "audio": audio_b64,
            "transcript": SESSIONS.get(session_id, ""),
        }

    # Neues Transkript zur Session hinzufügen.
    full_transcript = (SESSIONS.get(session_id, "") + " " + transcript_part).strip()
    SESSIONS[session_id] = full_transcript

    # Rechnungsdaten aus dem bisherigen Gespräch extrahieren.
    invoice_json = extract_invoice_context(full_transcript)
    parse_error = False
    try:
        invoice = parse_invoice_context(invoice_json)
    except ValueError:
        parse_error = True
        invoice = INVOICE_STATE.get(
            session_id,
            InvoiceContext(
                type="InvoiceContext", customer={}, service={}, items=[], amount={}
            ),
        )

    # Platzhalter und geschätzte Arbeitszeit ergänzen.
    fill_default_fields(invoice)
    if not any(item.category == "labor" for item in invoice.items):
        invoice.items.append(
            estimate_labor_item(invoice.service.get("description", ""))
        )

    apply_pricing(invoice)

    INVOICE_STATE[session_id] = invoice

    missing = [f for f in missing_invoice_fields(invoice) if f != "amount.total"]
    # Wenn ausschließlich Kunden-/Serviceangaben fehlen, reicht der Platzhalter aus.
    if set(missing).issubset({"customer.name", "service.description"}):
        missing = []

    log_dir = store_interaction(audio_bytes, full_transcript, invoice)
    pdf_path = str(Path(log_dir) / "invoice.pdf")
    pdf_url = "/" + pdf_path.replace("\\", "/")

    if parse_error and session_id in INVOICE_STATE:
        question = "Wie viele Stunden wurden abgerechnet?"
        audio_b64 = base64.b64encode(text_to_speech(question)).decode("ascii")
        return {
            "done": False,
            "question": question,
            "audio": audio_b64,
            "transcript": full_transcript,
            "invoice": invoice.model_dump(mode="json"),
            "log_dir": log_dir,
            "pdf_path": pdf_path,
            "pdf_url": pdf_url,
        }

    if missing:
        invoice = INVOICE_STATE.get(session_id, invoice)
        question_map = {
            "customer.name": "Wie heißt der Kunde?",
            "service.description": "Welche Dienstleistung wurde erbracht?",
            "items": "Welche Positionen wurden abgerechnet?",
        }
        question_lines = [question_map.get(f, f) for f in missing]
        question = "\n".join(question_lines)
        audio_b64 = base64.b64encode(text_to_speech(question)).decode("ascii")
        return {
            "done": False,
            "question": question,
            "audio": audio_b64,
            "transcript": full_transcript,
            "invoice": invoice.model_dump(mode="json"),
            "log_dir": log_dir,
            "pdf_path": pdf_path,
            "pdf_url": pdf_url,
        }

    # Alle Angaben vollständig – Rechnung erzeugen und Session aufräumen.
    send_to_billing_system(invoice)
    message = (
        "Vorläufige Rechnung für "
        f"{invoice.customer['name']} über {invoice.amount['total']} Euro erstellt."
    )
    audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
    return {
        "done": True,
        "message": message,
        "audio": audio_b64,
        "invoice": invoice.model_dump(mode="json"),
        "log_dir": log_dir,
        "pdf_path": pdf_path,
        "pdf_url": pdf_url,
        "transcript": full_transcript,
    }

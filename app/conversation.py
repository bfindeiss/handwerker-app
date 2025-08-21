"""Dialogbasierte Erfassung von Rechnungsdaten."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, File, Form, UploadFile

from app.billing_adapter import send_to_billing_system
from app.llm_agent import extract_invoice_context
from app.models import (
    InvoiceContext,
    InvoiceItem,
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
SESSIONS: Dict[str, List[Dict[str, str]]] = {}
# Zuletzt erfolgreicher Rechnungszustand pro Session
INVOICE_STATE: Dict[str, InvoiceContext] = {}

# Pfad zur Konfigurationsdatei
ENV_PATH = Path(".env")

# Platzhalter, die von LLMs häufig für Kundennamen verwendet werden
_CUSTOMER_NAME_PLACEHOLDERS = {
    "john doe",
    "jane doe",
    "max mustermann",
    "erika mustermann",
}


def _user_set_customer_name(name: str | None, transcript: str | None = None) -> bool:
    """Prüft, ob ein Kundenname vom Nutzer stammt."""

    if not name:
        return False

    lowered = name.strip().casefold()
    if lowered in _CUSTOMER_NAME_PLACEHOLDERS:
        return False

    if transcript is not None and lowered not in transcript.casefold():
        return False

    return True


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


def merge_invoice_data(existing: InvoiceContext, new: InvoiceContext) -> InvoiceContext:
    """Merge ``new`` invoice data into ``existing`` without overwriting user input.

    Bereits gesetzte Werte im bestehenden Rechnungszustand bleiben erhalten.
    Neue Positionen werden hinzugefügt und fehlende Details ergänzt. Mengen
    oder Preise werden nur überschrieben, wenn sie im bestehenden Zustand
    noch nicht gesetzt waren (z.\u202fB. 0 als Platzhalter).
    """

    merged = existing.model_copy(deep=True)

    item_map = {(i.category, i.description, i.worker_role): i for i in merged.items}

    def _is_generic_material(desc: str) -> bool:
        return desc.lower() in {"material", "materialkosten"}

    def _is_placeholder_labor(it: InvoiceItem) -> bool:
        return (
            it.category == "labor"
            and it.description.lower().startswith("arbeitszeit")
            and not it.unit_price
        )

    service_placeholder = merged.service.get("description") in (
        None,
        "",
        "Dienstleistung nicht näher beschrieben",
    )

    for item in new.items:
        key = (item.category, item.description, item.worker_role)

        if item.category == "labor":
            placeholders = [
                ex
                for ex in merged.items
                if _is_placeholder_labor(ex)
                and ex.worker_role == item.worker_role
                and ex.description != item.description
            ]
            for ph in placeholders:
                merged.items.remove(ph)
                item_map.pop((ph.category, ph.description, ph.worker_role), None)

        if item.category == "material":
            placeholders = [
                ex
                for ex in merged.items
                if ex.category == "material" and _is_generic_material(ex.description)
            ]
            for ph in placeholders:
                merged.items.remove(ph)
                item_map.pop((ph.category, ph.description, ph.worker_role), None)

            if _is_generic_material(item.description):
                existing_specific = [
                    ex for ex in merged.items if ex.category == "material"
                ]
                if existing_specific:
                    target = existing_specific[0]
                    if not target.quantity and item.quantity:
                        target.quantity = item.quantity
                    if not target.unit_price and item.unit_price:
                        target.unit_price = item.unit_price
                    if not target.unit and item.unit:
                        target.unit = item.unit
                    continue

        existing_item = item_map.get(key)
        if existing_item:
            if service_placeholder:
                if item.quantity:
                    existing_item.quantity = item.quantity
                if item.unit_price:
                    existing_item.unit_price = item.unit_price
                if item.unit:
                    existing_item.unit = item.unit
            else:
                if not existing_item.quantity and item.quantity:
                    existing_item.quantity = item.quantity
                if not existing_item.unit_price and item.unit_price:
                    existing_item.unit_price = item.unit_price
                if not existing_item.unit and item.unit:
                    existing_item.unit = item.unit
        else:
            merged.items.append(item)
            item_map[key] = item

    if (
        merged.customer.get("name") in (None, "", "Unbekannter Kunde")
        and _user_set_customer_name(new.customer.get("name"))
    ):

        merged.customer["name"] = new.customer["name"]
    if merged.service.get("description") in (
        None,
        "",
        "Dienstleistung nicht näher beschrieben",
    ) and new.service.get("description"):
        merged.service["description"] = new.service["description"]

    return merged


def fill_default_fields(invoice: InvoiceContext) -> None:
    """Ergänzt fehlende Pflichtfelder durch Platzhalter."""

    if not invoice.customer.get("name"):
        invoice.customer["name"] = "Unbekannter Kunde"
    if not invoice.service.get("description"):
        invoice.service["description"] = "Dienstleistung nicht näher beschrieben"


def _handle_conversation(
    session_id: str, transcript_part: str, audio_bytes: bytes
) -> dict:
    """Gemeinsame Logik für Sprach- und Texteingaben."""

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
            "transcript": " ".join(
                m["content"] for m in SESSIONS.get(session_id, [])
            ),
        }

    # Prüft auf Befehle wie "Position X löschen".
    m = re.search(r"position\s+(\d+)\s+löschen", transcript_part, re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        invoice = INVOICE_STATE.get(session_id)
        if invoice and 1 <= idx <= len(invoice.items):
            del invoice.items[idx - 1]
            apply_pricing(invoice)
            INVOICE_STATE[session_id] = invoice
            message = f"Position {idx} gelöscht."
        else:
            message = f"Position {idx} nicht gefunden."
        audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
        return {
            "done": False,
            "message": message,
            "audio": audio_b64,
            "transcript": SESSIONS.get(session_id, ""),
        }

    # Neues Transkript zur Session hinzufügen.
    session_msgs = SESSIONS.setdefault(session_id, [])
    session_msgs.append({"role": "user", "content": transcript_part})
    full_transcript = " ".join(
        m["content"] for m in session_msgs if m["role"] == "user"
    )

    # Rechnungsdaten aus dem bisherigen Gespräch extrahieren.
    had_state = session_id in INVOICE_STATE
    invoice_json = extract_invoice_context(full_transcript)
    parse_error = False
    placeholder_notice = False
    try:
        parsed = parse_invoice_context(invoice_json)
        if not _user_set_customer_name(
            parsed.customer.get("name"), full_transcript
        ):
            parsed.customer.pop("name", None)
        if had_state:
            invoice = merge_invoice_data(INVOICE_STATE[session_id], parsed)
        else:
            invoice = parsed
    except ValueError:
        parse_error = True
        if had_state:
            invoice = INVOICE_STATE[session_id]
        else:
            distance = 0.0
            m_distance = re.search(
                r"(\d+(?:[.,]\d+)?)\s*(?:km|kilometer)",
                full_transcript,
                re.IGNORECASE,
            )
            if m_distance:
                distance = float(m_distance.group(1).replace(",", "."))

            invoice = InvoiceContext(
                type="InvoiceContext",
                customer={"name": "Unbekannter Kunde"},
                service={"description": "Dienstleistung nicht näher beschrieben"},
                items=[
                    InvoiceItem(
                        description="Arbeitszeit Geselle",
                        category="labor",
                        quantity=1.0,
                        unit="h",
                        unit_price=0.0,
                        worker_role="Geselle",
                    ),
                    InvoiceItem(
                        description="Material",
                        category="material",
                        quantity=0.0,
                        unit="stk",
                        unit_price=0.0,
                    ),
                    InvoiceItem(
                        description="Anfahrt",
                        category="travel",
                        quantity=distance,
                        unit="km",
                        unit_price=0.0,
                    ),
                ],
                amount={},
            )
            apply_pricing(invoice)
            INVOICE_STATE[session_id] = invoice
            placeholder_notice = True

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

    if parse_error and had_state:
        if "stund" in invoice_json.lower():
            question = "Wie viele Stunden wurden abgerechnet?"
        else:
            question = "Welche Positionen wurden abgerechnet?"
        session_msgs.append({"role": "assistant", "content": question})
        log_dir = store_interaction(audio_bytes, session_msgs, invoice)
        pdf_path = str(Path(log_dir) / "invoice.pdf")
        pdf_url = "/" + pdf_path.replace("\\", "/")
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
        session_msgs.append({"role": "assistant", "content": question})
        log_dir = store_interaction(audio_bytes, session_msgs, invoice)
        pdf_path = str(Path(log_dir) / "invoice.pdf")
        pdf_url = "/" + pdf_path.replace("\\", "/")
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
    if placeholder_notice:
        message = "Hinweis: Platzhalter verwendet. " + message
    session_msgs.append({"role": "assistant", "content": message})
    log_dir = store_interaction(audio_bytes, session_msgs, invoice)
    pdf_path = str(Path(log_dir) / "invoice.pdf")
    pdf_url = "/" + pdf_path.replace("\\", "/")
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


@router.post("/conversation/")
async def voice_conversation(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Führt eine dialogorientierte Aufnahme durch."""

    audio_bytes = await file.read()
    transcript_part = transcribe_audio(audio_bytes)
    return _handle_conversation(session_id, transcript_part, audio_bytes)


@router.post("/conversation-text/")
async def text_conversation(session_id: str = Form(...), text: str = Form(...)):
    """Dialog über Texteingabe."""

    return _handle_conversation(session_id, text, b"")

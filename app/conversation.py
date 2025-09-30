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
from app.summaries import build_invoice_summary
from app.stt import transcribe_audio
from app.tts import text_to_speech

router = APIRouter()

# Zwischenspeicher für laufende Konversationen
SESSIONS: Dict[str, List[Dict[str, str]]] = {}
# Zuletzt erfolgreicher Rechnungszustand pro Session
INVOICE_STATE: Dict[str, InvoiceContext] = {}
# Fortschritt der jeweiligen Session (z. B. "collecting", "summarizing")
SESSION_STATUS: Dict[str, str] = {}
# Noch nicht bestätigte Rechnungsentwürfe
PENDING_CONFIRMATION: Dict[str, Dict[str, object]] = {}

# Pfad zur Konfigurationsdatei
ENV_PATH = Path(".env")

# Platzhalter, die von LLMs häufig für Kundennamen verwendet werden
_CUSTOMER_NAME_PLACEHOLDERS = {
    "john doe",
    "jane doe",
    "max mustermann",
    "erika mustermann",
}

_ROLE_KEYWORDS = {
    r"\bmeister\b": "Meister",
    r"\bmeisterstund": "Meister",
    r"\bgesell": "Geselle",
    r"\bazub": "Azubi",
    r"\blehrling": "Azubi",
}

_LABOR_ROLE_LABELS = {
    "meister": "Meister",
    "gesell": "Geselle",
    "azub": "Azubi",
}

_LABOR_QUANTITY_PATTERNS = [
    (
        re.compile(
            r"(\d+(?:[.,]\d+)?)\s*(meister|gesell(?:e|en)?|azub(?:i|is)?)\w*",
            re.IGNORECASE,
        ),
        1,
        2,
    ),
    (
        re.compile(
            r"(meister|gesell(?:e|en)?|azub(?:i|is)?)\w*\s*(?:von\s+|für\s+)?(\d+(?:[.,]\d+)?)\s*(?:stunden|std|h)",
            re.IGNORECASE,
        ),
        2,
        1,
    ),
]

_MATERIAL_PRICE_PATTERN = re.compile(
    r"(?:die|der|das|den|ein|eine|einen|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|\d+)\s+"
    r"((?:[a-zäöüß-]+(?:\s+[a-zäöüß-]+){0,2}))\s+(?:je|für|zu|kostet(?:en)?|waren|war)\s+"
    r"(\d+(?:[.,]\d+)?)\s*(?:€|eur|euro)",
    re.IGNORECASE,
)

_MATERIAL_COUNT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:x\s*)?([a-zäöüß][a-zäöüß-]*)",
    re.IGNORECASE,
)

_ITEM_CORRECTION_PATTERN = re.compile(
    r"position\s+(?P<index>\d+)(?:\s+(?P<field>menge|preis|beschreibung))?"
    r"\s*(?:ist|sind|auf|zu|soll(?:\s+sein)?|beträgt|=)?\s*(?P<value>.+)",
    re.IGNORECASE,
)
_CUSTOMER_CORRECTION_PATTERN = re.compile(
    r"kunde\s+(?:ist|heißt)\s+(?P<value>.+)",
    re.IGNORECASE,
)
_SERVICE_CORRECTION_PATTERN = re.compile(
    r"dienstleistung\s+(?:ist|lautet)\s+(?P<value>.+)",
    re.IGNORECASE,
)


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


def _labor_hours_from_transcript(transcript: str) -> dict[str, float]:
    """Extrahiert Arbeitsstunden pro Rolle aus dem Gesprächstext."""

    hours: dict[str, float] = {}
    if not transcript:
        return hours

    for pattern, qty_index, role_index in _LABOR_QUANTITY_PATTERNS:
        for match in pattern.finditer(transcript):
            qty_str = match.group(qty_index)
            role_raw = match.group(role_index)

            if not qty_str or not role_raw:
                continue

            role_key = role_raw.casefold()
            label = None
            for key, value in _LABOR_ROLE_LABELS.items():
                if key in role_key:
                    label = value
                    break

            if not label:
                continue

            tail = match.group(0).casefold()
            if "stund" not in tail and not re.search(r"\b(h|std)\b", tail):
                # Stellen wie "2 Meister" ohne Stundenangabe ignorieren.
                continue

            try:
                qty = float(qty_str.replace(",", "."))
            except ValueError:  # pragma: no cover - defensive
                continue

            hours[label] = hours.get(label, 0.0) + qty

    return hours


def _extract_customer_name(transcript: str) -> str | None:
    """Versucht den Kundennamen aus Formulierungen wie 'bei Hr. ...' zu lesen."""

    if not transcript:
        return None

    pattern = re.compile(
        r"bei\s+(?:herrn?|herr|hr\.?|frau|fr\.?|firma)?\s*([a-zäöüß'\-\s]+?)(?=\s+(?:in|am|auf|an|mit|und|,|\.|$))",
        re.IGNORECASE,
    )
    match = pattern.search(transcript)
    if not match:
        return None

    name = match.group(1).strip()
    if not name:
        return None

    # Entfernt eventuell führende Artikel wie "der" oder "die" innerhalb des Namens.
    name = re.sub(r"^(der|die|das)\s+", "", name, flags=re.IGNORECASE)
    return name.title()


def _normalize_material_key(word: str) -> list[str]:
    """Erzeugt Vergleichsvarianten für Materialbeschreibungen."""

    variants: list[str] = []
    lowered = word.casefold()
    if lowered:
        variants.append(lowered)
    for suffix in ("ern", "en", "n"):
        if lowered.endswith(suffix) and len(lowered) > len(suffix) + 1:
            shortened = lowered[: -len(suffix)]
            if shortened and shortened not in variants:
                variants.append(shortened)
    return variants


def _material_counts_from_transcript(transcript: str) -> dict[str, float]:
    """Sucht nach Mengenangaben wie '2 Fenster'."""

    counts: dict[str, float] = {}
    if not transcript:
        return counts

    skip_words = {
        "km",
        "kilometer",
        "kilometern",
        "stunden",
        "stunde",
        "std",
        "meisterstunden",
        "gesellenstunden",
    }

    for match in _MATERIAL_COUNT_PATTERN.finditer(transcript):
        qty_str, word = match.groups()
        if not qty_str or not word:
            continue

        normalized_forms = _normalize_material_key(word)
        if any(form in skip_words for form in normalized_forms):
            continue

        try:
            qty = float(qty_str.replace(",", "."))
        except ValueError:  # pragma: no cover - defensive
            continue

        for form in normalized_forms:
            counts[form] = qty

    return counts


def _ensure_material_items_from_transcript(
    invoice: InvoiceContext, transcript: str
) -> bool:
    """Ergänzt fehlende Materialpositionen aus einfachen Textmustern.

    Gibt ``True`` zurück, wenn Angaben aus dem Transkript übernommen wurden.
    """

    if not transcript:
        return False

    existing = {
        item.description.casefold(): item
        for item in invoice.items
        if item.category == "material"
    }
    counts = _material_counts_from_transcript(transcript)

    changed = False

    for match in _MATERIAL_PRICE_PATTERN.finditer(transcript):
        raw_desc, price_str = match.groups()
        if not raw_desc or not price_str:
            continue

        desc = raw_desc.strip()
        key = desc.casefold()
        try:
            price = float(price_str.replace(",", "."))
        except ValueError:  # pragma: no cover - defensive
            continue

        quantity = 1.0
        for form in _normalize_material_key(desc):
            if form in counts:
                quantity = counts[form]
                break

        item = existing.get(key)

        if item:
            if not item.quantity:
                item.quantity = quantity
                changed = True
            if not item.unit_price:
                item.unit_price = price
                changed = True
            if not item.unit:
                item.unit = "Stk"
                changed = True
        else:
            new_item = InvoiceItem(
                description=desc.title(),
                category="material",
                quantity=quantity,
                unit="Stk",
                unit_price=price,
            )
            invoice.items.append(new_item)
            existing[key] = new_item
            changed = True

    if any(item.category == "material" for item in invoice.items):
        invoice.service.setdefault("materialIncluded", True)

    if changed:
        invoice.items = [
            item
            for item in invoice.items
            if not (
                item.category == "material"
                and item.description.casefold() in {"material", "materialkosten"}
                and (item.quantity or 0.0) == 0.0
                and (item.unit_price or 0.0) == 0.0
            )
        ]

    return changed


def _ensure_labor_items_from_transcript(
    invoice: InvoiceContext, transcript: str
) -> bool:
    """Legt Arbeitspositionen anhand erkannter Stunden an.

    Gibt ``True`` zurück, wenn Angaben aus dem Transkript übernommen wurden.
    """

    hours = _labor_hours_from_transcript(transcript)
    if not hours:
        return False

    changed = False

    for item in invoice.items:
        if item.category == "labor" and item.worker_role:
            key = item.worker_role.casefold()
            for pattern, label in _LABOR_ROLE_LABELS.items():
                if pattern in key and label in hours and not item.quantity:
                    item.quantity = hours[label]
                    changed = True

    for role, qty in hours.items():
        if qty <= 0:
            continue
        existing = next(
            (
                item
                for item in invoice.items
                if item.category == "labor" and (item.worker_role or "").casefold() == role.casefold()
            ),
            None,
        )
        if existing:
            if not existing.quantity:
                existing.quantity = qty
                changed = True
            if not existing.unit:
                existing.unit = "h"
                changed = True
            continue

        invoice.items.append(
            InvoiceItem(
                description=f"Arbeitszeit {role}",
                category="labor",
                quantity=qty,
                unit="h",
                unit_price=0.0,
                worker_role=role,
            )
        )
        changed = True

    return changed

def merge_invoice_data(
    existing: InvoiceContext,
    new: InvoiceContext,
    allow_overwrite: bool = False,
) -> InvoiceContext:
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
            if allow_overwrite:
                if item.quantity is not None:
                    existing_item.quantity = item.quantity
                if item.unit_price is not None:
                    existing_item.unit_price = item.unit_price
                if item.unit:
                    existing_item.unit = item.unit
            elif service_placeholder or not existing_item.unit_price:
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
    if not merged.customer.get("address") and new.customer.get("address"):
        merged.customer["address"] = new.customer["address"]
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


def _parse_number(value: str) -> float | None:
    """Extrahiert eine Fließkommazahl aus einem Textfragment."""

    if not value:
        return None

    compact = value.replace(" ", "").strip()
    match = re.search(r"\d+(?:[.,]\d+)?", compact)
    if not match:
        return None

    number = match.group(0)
    normalized = number.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:  # pragma: no cover - defensive
        return None


def _clean_command_value(value: str) -> str:
    """Bereinigt extrahierte Werte aus Korrekturkommandos."""

    if not value:
        return ""

    text = value.strip()
    for sep in (". ", "! ", "? ", "; "):
        idx = text.find(sep)
        if idx != -1:
            text = text[:idx]
            break
    text = text.strip()
    return text.rstrip(".?!;").strip()


def update_item_field(
    invoice: InvoiceContext, index: int, field: str, value: str
) -> tuple[bool, str]:
    """Aktualisiert Menge, Preis oder Beschreibung einer Rechnungsposition."""

    if not 1 <= index <= len(invoice.items):
        return False, f"Position {index} konnte ich nicht finden."

    item = invoice.items[index - 1]
    field_key = field.casefold()

    if field_key == "menge":
        number = _parse_number(value)
        if number is None:
            return False, f"Die Menge für Position {index} konnte ich nicht verstehen."
        item.quantity = number
        message = f"Menge in Position {index} ist jetzt {number:g}"
    elif field_key == "preis":
        number = _parse_number(value)
        if number is None:
            return False, f"Den Preis für Position {index} konnte ich nicht verstehen."
        item.unit_price = number
        message = f"Preis in Position {index} ist jetzt {number:g} Euro"
    elif field_key == "beschreibung":
        text = value.strip()
        if not text:
            return False, "Bitte gib eine Beschreibung an."
        item.description = text
        message = f"Beschreibung in Position {index} aktualisiert"
    else:  # pragma: no cover - defensive
        return False, f"Feld '{field}' kann ich nicht anpassen."

    apply_pricing(invoice)
    fill_default_fields(invoice)
    return True, message


def update_customer_name(invoice: InvoiceContext, value: str) -> tuple[bool, str]:
    """Aktualisiert den Kundennamen."""

    name = value.strip()
    if not name:
        return False, "Bitte nenne einen Kundennamen."
    invoice.customer["name"] = name
    apply_pricing(invoice)
    fill_default_fields(invoice)
    return True, f"Kunde ist jetzt {name}"


def update_service_description(invoice: InvoiceContext, value: str) -> tuple[bool, str]:
    """Aktualisiert die Dienstleistungsbeschreibung."""

    description = value.strip()
    if not description:
        return False, "Bitte nenne eine Dienstleistung."
    invoice.service["description"] = description
    apply_pricing(invoice)
    fill_default_fields(invoice)
    return True, f"Dienstleistung lautet jetzt {description}"


def _normalize_worker_role(role: str | None) -> str | None:
    """Bringt Rollenbezeichnungen auf eine einheitliche Schreibweise."""

    if not role:
        return None

    text = role.strip().casefold()
    for pattern, label in _ROLE_KEYWORDS.items():
        if re.search(pattern, text):
            return label
    return role.strip() or None


def _roles_from_transcript(transcript: str) -> set[str]:
    """Erkennt erwähnte Handwerkerrollen im Gespräch."""

    roles: set[str] = set()
    lowered = transcript or ""
    for pattern, label in _ROLE_KEYWORDS.items():
        if re.search(pattern, lowered, re.IGNORECASE):
            roles.add(label)
    return roles


def _handle_direct_corrections(session_id: str, transcript_part: str) -> dict | None:
    """Verarbeitet erkannte Korrekturbefehle ohne LLM-Roundtrip."""

    invoice = INVOICE_STATE.get(session_id)
    if not invoice:
        return None

    text = transcript_part or ""
    handled = False
    updated = False
    feedback: list[str] = []

    for match in _ITEM_CORRECTION_PATTERN.finditer(text):
        handled = True
        idx = int(match.group("index"))
        field = match.group("field") or "menge"
        raw_value = _clean_command_value(match.group("value"))
        success, message = update_item_field(invoice, idx, field, raw_value)
        feedback.append(message)
        if success:
            updated = True

    customer_match = _CUSTOMER_CORRECTION_PATTERN.search(text)
    if customer_match:
        handled = True
        raw = _clean_command_value(customer_match.group("value"))
        success, message = update_customer_name(invoice, raw)
        feedback.append(message)
        if success:
            updated = True

    service_match = _SERVICE_CORRECTION_PATTERN.search(text)
    if service_match:
        handled = True
        raw = _clean_command_value(service_match.group("value"))
        success, message = update_service_description(invoice, raw)
        feedback.append(message)
        if success:
            updated = True

    if not handled:
        return None

    INVOICE_STATE[session_id] = invoice

    def _ensure_period(message: str) -> str:
        trimmed = message.strip()
        if not trimmed:
            return ""
        if trimmed[-1] not in ".!?":
            return trimmed + "."
        return trimmed

    spoken = " ".join(filter(None, (_ensure_period(msg) for msg in feedback)))
    if updated:
        SESSION_STATUS[session_id] = "collecting"
        spoken = (spoken + " Ich fasse gleich neu zusammen.").strip()
    else:
        SESSION_STATUS.setdefault(session_id, "collecting")

    session_msgs = SESSIONS.setdefault(session_id, [])
    session_msgs.append({"role": "user", "content": transcript_part})

    audio_b64 = base64.b64encode(text_to_speech(spoken)).decode("ascii")

    current_transcript = " ".join(
        m["content"] for m in session_msgs if m.get("role") == "user"
    )

    return dict(
        done=False,
        message=spoken,
        audio=audio_b64,
        invoice=invoice.model_dump(mode="json"),
        transcript=current_transcript,
        session_status=SESSION_STATUS.get(session_id, "collecting"),
    )


def _build_invoice_summary(
    invoice: InvoiceContext, placeholder_notice: bool = False
) -> str:
    """Erstellt eine kurze Zusammenfassung der Rechnungsdaten."""

    customer = invoice.customer.get("name") or "Unbekannter Kunde"
    service = invoice.service.get("description") or "Ohne Beschreibung"
    currency = invoice.amount.get("currency", "EUR")
    total = invoice.amount.get("total", 0.0)
    item_lines = []
    for idx, item in enumerate(invoice.items, start=1):
        unit = item.unit or ""
        unit = f" {unit}" if unit else ""
        price = f" zu {item.unit_price:.2f} EUR" if item.unit_price else ""
        quantity = f"{item.quantity:g}{unit}" if item.quantity is not None else "-"
        role = f" ({item.worker_role})" if item.worker_role else ""
        item_lines.append(
            f"{idx}. {item.description}{role}: {quantity}{price}"
        )

    items_text = "\n".join(item_lines) if item_lines else "Keine Positionen erfasst."
    summary_lines = [
        "Bitte bestätigen Sie die folgenden Rechnungsdaten:",
        f"Kunde: {customer}",
        f"Leistung: {service}",
        "Positionen:",
        items_text,
        f"Gesamtbetrag: {total:.2f} {currency}",
    ]
    if placeholder_notice:
        summary_lines.append(
            "Hinweis: Teile der Rechnung basieren noch auf Platzhaltern."
        )
    return "\n".join(summary_lines)


def _is_confirmation(text: str) -> bool:
    """Erkennt einfache Bestätigungen im Nutzereingang."""

    if not text:
        return False

    lowered = text.casefold()
    confirmation_keywords = {
        "ja",
        "passt",
        "in ordnung",
        "bestätige",
        "bestätigt",
        "klingt gut",
        "genau so",
        "alles klar",
    }
    return any(keyword in lowered for keyword in confirmation_keywords)


def _handle_conversation(
    session_id: str, transcript_part: str, audio_bytes: bytes
) -> dict:
    """Gemeinsame Logik für Sprach- und Texteingaben."""

    SESSION_STATUS.setdefault(session_id, "collecting")

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
        return dict(
            done=False,
            message=message,
            audio=audio_b64,
            transcript=" ".join(
                m["content"] for m in SESSIONS.get(session_id, [])
            ),
        )

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
            SESSION_STATUS[session_id] = "collecting"
        else:
            message = f"Position {idx} nicht gefunden."
        audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
        if invoice and not _user_set_customer_name(invoice.customer.get("name"), transcript_part):
            invoice.customer.pop("name", None)
            fill_default_fields(invoice)
        return dict(
            done=False,
            message=message,
            audio=audio_b64,
            transcript=SESSIONS.get(session_id, ""),
            invoice=invoice.model_dump(mode="json") if invoice else None,
            session_status=SESSION_STATUS.get(session_id, "collecting"),
        )

    correction = _handle_direct_corrections(session_id, transcript_part)
    if correction:
        return correction

    # Neues Transkript zur Session hinzufügen.
    session_msgs = SESSIONS.setdefault(session_id, [])
    session_msgs.append({"role": "user", "content": transcript_part})
    full_transcript = " ".join(
        m["content"] for m in session_msgs if m["role"] == "user"
    )

    overwrite_existing = False
    pending = PENDING_CONFIRMATION.get(session_id)
    if pending:
        if _is_confirmation(transcript_part):
            invoice = pending["invoice"]
            summary = pending["summary"]
            send_to_billing_system(invoice)
            detailed_summary = build_invoice_summary(invoice)
            message = (
                "Rechnung bestätigt und finalisiert. "
                f"{detailed_summary} "
                "Ich habe die vorläufige Rechnung erstellt und an das Abrechnungssystem übergeben."
            )
            session_msgs.append({"role": "assistant", "content": message})
            log_dir = store_interaction(audio_bytes, session_msgs, invoice)
            pdf_path = str(Path(log_dir) / "invoice.pdf")
            pdf_url = "/" + pdf_path.replace("\\", "/")
            audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
            PENDING_CONFIRMATION.pop(session_id, None)
            SESSION_STATUS[session_id] = "completed"
            return {
                "done": True,
                "message": message,
                "summary": summary,
                "status": "confirmed",
                "audio": audio_b64,
                "invoice": invoice.model_dump(mode="json"),
                "log_dir": log_dir,
                "pdf_path": pdf_path,
                "pdf_url": pdf_url,
                "transcript": full_transcript,
            }

        # Jede andere Eingabe interpretiert das System als Korrektur.
        PENDING_CONFIRMATION.pop(session_id, None)
        overwrite_existing = True

    distance = 0.0
    m_distance = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:km|kilometer)",
        full_transcript,
        re.IGNORECASE,
    )
    if m_distance:
        distance = float(m_distance.group(1).replace(",", "."))

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
            invoice = merge_invoice_data(
                INVOICE_STATE[session_id], parsed, allow_overwrite=overwrite_existing
            )
        else:
            invoice = parsed
    except ValueError:
        parse_error = True
        if had_state:
            invoice = INVOICE_STATE[session_id]
        else:
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
            placeholder_notice = True

    # Rollen aus dem Gespräch ableiten.
    detected_roles = _roles_from_transcript(transcript_part)
    if not detected_roles:
        detected_roles = _roles_from_transcript(full_transcript)
    for item in invoice.items:
        normalized = _normalize_worker_role(item.worker_role)
        if normalized != item.worker_role:
            item.worker_role = normalized

    labor_items_without_role = [
        item for item in invoice.items if item.category == "labor" and not item.worker_role
    ]
    ambiguous_roles = False
    if labor_items_without_role:
        if len(detected_roles) == 1:
            assigned_role = next(iter(detected_roles))
            for item in labor_items_without_role:
                item.worker_role = assigned_role
        elif len(detected_roles) > 1:
            ambiguous_roles = True

    labor_inferred = _ensure_labor_items_from_transcript(invoice, full_transcript)
    material_inferred = _ensure_material_items_from_transcript(invoice, full_transcript)

    # Platzhalter und geschätzte Arbeitszeit ergänzen.
    travel_item = next((i for i in invoice.items if i.category == "travel"), None)
    if not travel_item:
        invoice.items.append(
            InvoiceItem(
                description="Anfahrt",
                category="travel",
                quantity=distance,
                unit="km",
                unit_price=0.0,
            )
        )
    elif distance:
        travel_item.quantity = distance

    if not invoice.customer.get("name"):
        extracted_name = _extract_customer_name(full_transcript)
        if _user_set_customer_name(extracted_name, full_transcript):
            invoice.customer["name"] = extracted_name

    fill_default_fields(invoice)
    if not any(item.category == "labor" for item in invoice.items):
        invoice.add_item(
            estimate_labor_item(invoice.service.get("description", ""))
        )

    apply_pricing(invoice)

    if placeholder_notice and (labor_inferred or material_inferred):
        placeholder_notice = False

    INVOICE_STATE[session_id] = invoice

    if ambiguous_roles:
        role_list = ", ".join(sorted(detected_roles)) or "verschiedene Rollen"
        question = (
            "Ich habe mehrere Rollen im Gespräch gehört ("
            f"{role_list}"
            "). Für welche Rolle sollen die Arbeitsstunden berechnet werden?"
        )
        already_asked = any(
            msg.get("content") == question and msg.get("role") == "assistant"
            for msg in session_msgs
        )
        if not already_asked:
            session_msgs.append({"role": "assistant", "content": question})
        log_dir = store_interaction(audio_bytes, session_msgs, invoice)
        pdf_path = str(Path(log_dir) / "invoice.pdf")
        pdf_url = "/" + pdf_path.replace("\\", "/")
        audio_b64 = base64.b64encode(text_to_speech(question)).decode("ascii")
        return dict(
            done=False,
            question=question,
            audio=audio_b64,
            transcript=full_transcript,
            invoice=invoice.model_dump(mode="json"),
            log_dir=log_dir,
            pdf_path=pdf_path,
            pdf_url=pdf_url,
        )

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
        return dict(
            done=False,
            question=question,
            audio=audio_b64,
            transcript=full_transcript,
            invoice=invoice.model_dump(mode="json"),
            log_dir=log_dir,
            pdf_path=pdf_path,
            pdf_url=pdf_url,
        )

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
        return dict(
            done=False,
            question=question,
            audio=audio_b64,
            transcript=full_transcript,
            invoice=invoice.model_dump(mode="json"),
            log_dir=log_dir,
            pdf_path=pdf_path,
            pdf_url=pdf_url,
        )

    if placeholder_notice:
        message = (
            "Ich habe bislang nur Platzhalter für Arbeitszeit, Material und Anfahrt "
            "eingesetzt. Bitte beschreibe die tatsächlichen Positionen."
        )
        session_msgs.append({"role": "assistant", "content": message})
        log_dir = store_interaction(audio_bytes, session_msgs, invoice)
        pdf_path = str(Path(log_dir) / "invoice.pdf")
        pdf_url = "/" + pdf_path.replace("\\", "/")
        audio_b64 = base64.b64encode(text_to_speech(message)).decode("ascii")
        return dict(
            done=False,
            message=message,
            audio=audio_b64,
            invoice=invoice.model_dump(mode="json"),
            log_dir=log_dir,
            pdf_path=pdf_path,
            pdf_url=pdf_url,
            transcript=full_transcript,
        )

    # Alle Angaben vollständig – Zusammenfassung schicken und Bestätigung abwarten.
    summary = _build_invoice_summary(invoice, placeholder_notice)
    session_msgs.append({"role": "assistant", "content": summary})
    PENDING_CONFIRMATION[session_id] = {
        "invoice": invoice.model_copy(deep=True),
        "summary": summary,
    }
    log_dir = store_interaction(audio_bytes, session_msgs, invoice)
    pdf_path = str(Path(log_dir) / "invoice.pdf")
    pdf_url = "/" + pdf_path.replace("\\", "/")
    audio_b64 = base64.b64encode(text_to_speech(summary)).decode("ascii")
    SESSION_STATUS[session_id] = "awaiting_confirmation"
    return {
        "done": False,
        "status": "awaiting_confirmation",
        "summary": summary,
        "message": summary,
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

from __future__ import annotations

from pathlib import Path
import re

import yaml

from app.models import InvoiceItem
from app.service_templates import SERVICE_TEMPLATES


def estimate_labor_item(service_description: str) -> InvoiceItem:
    """Erzeugt eine Standard-Arbeitsposition basierend auf der Dienstleistung."""
    desc = (service_description or "").lower()
    hours = 1.0
    if "malen" in desc or "streichen" in desc:
        hours = 4.0
    elif "fenster" in desc:
        hours = 5.0
    elif "dusche" in desc:
        hours = 8.0
    return InvoiceItem(
        description="Arbeitszeit Geselle",
        category="labor",
        quantity=hours,
        unit="h",
        unit_price=0.0,
        worker_role="Geselle",
    )


def _load_rules() -> dict:
    """Lädt optionale Validierungsregeln für Rechnungspositionen."""

    rules_path = Path(__file__).with_name("invoice_rules.yaml")
    if not rules_path.exists():
        return {}
    with rules_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


RULES = _load_rules()


def generate_invoice_items(description: str) -> list[InvoiceItem]:
    """Erzeugt Rechnungspositionen aus freiem Text.

    Aktuell wird eine einfache Regex-basierte Logik verwendet und
    optionalen Validierungs-vorgaben aus ``invoice_rules.yaml``
    gefolgt. Bei fehlenden Angaben oder Regelverletzungen wird
    ``ValueError`` ausgelöst.
    """

    if not description or not description.strip():
        raise ValueError("empty description")

    text = description.strip()
    desc_lower = text.lower()

    # Zuerst bekannte Dienstleistungs-Vorlagen prüfen.
    keyword_map = {
        "dusche": "dusche_einbauen",
        "duschkabine": "dusche_einbauen",
        "fenster": "fenster_setzen",
        "laminat": "laminat_verlegen",
        "steckdose": "steckdose_installieren",
        "malen": "waende_streichen",
        "streichen": "waende_streichen",
    }
    for keyword, template_key in keyword_map.items():
        if keyword in desc_lower and template_key in SERVICE_TEMPLATES:
            return [InvoiceItem(**data) for data in SERVICE_TEMPLATES[template_key]]

    # Parser für Eingaben wie "2 h Reinigung 30 EUR".
    pattern = re.compile(
        r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>\w+)\s+"  # Menge + Einheit
        r"(?P<desc>.+?)\s+"  # Beschreibung
        r"(?P<price>\d+(?:\.\d+)?)\s*eur",  # Preis
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError("parse error")

    quantity = float(match.group("qty"))
    unit = match.group("unit")
    item_desc = match.group("desc").strip()
    unit_price = float(match.group("price"))

    labor_units = {"h", "std", "stunde", "stunden"}
    category = "labor" if unit.lower() in labor_units else "material"

    # Validierungsregeln anwenden
    allowed_units = {u.lower() for u in RULES.get("allowed_units", [])}
    if allowed_units and unit.lower() not in allowed_units:
        raise ValueError("invalid unit")

    price_limits = RULES.get("price_limits", {})
    limit = price_limits.get(category)
    if limit is not None and unit_price > limit:
        raise ValueError("price exceeds limit")

    item = InvoiceItem(
        description=item_desc,
        category=category,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
    )
    return [item]


def estimate_invoice_items(service_description: str) -> list[InvoiceItem]:
    """Erzeugt Rechnungspositionen oder fällt auf eine generische Position zurück."""

    try:
        return generate_invoice_items(service_description)
    except ValueError:
        return [estimate_labor_item(service_description)]

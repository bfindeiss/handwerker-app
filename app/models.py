"""Datenmodelle für Rechnungen und Hilfsfunktionen."""

from pydantic import BaseModel, ValidationError
from typing import Literal, Optional
from datetime import date
import json
import re


class InvoiceItem(BaseModel):
    """Einzelne Rechnungsposition."""

    # Freitextbeschreibung der Position.
    description: str
    # Art der Leistung – wird später für die Rechnungsklasse genutzt.
    category: Literal["material", "travel", "labor"]
    quantity: float
    unit: str
    unit_price: float
    # Optional kann die Rolle des Mitarbeiters angegeben werden.
    worker_role: Optional[str] = None

    @property
    def total(self) -> float:
        """Gesamtpreis der Position (Menge × Einzelpreis)."""
        return self.quantity * self.unit_price


class InvoiceContext(BaseModel):
    """Gesamte, strukturierte Rechnung wie sie vom LLM geliefert wird."""

    type: str
    customer: dict
    service: dict
    items: list[InvoiceItem]
    amount: dict
    invoice_number: Optional[str] = None
    issue_date: Optional[date] = None


def parse_invoice_context(invoice_json: str) -> "InvoiceContext":
    """JSON-Text in das ``InvoiceContext``-Modell überführen."""

    if not invoice_json or not invoice_json.strip():
        raise ValueError("empty invoice context")

    cleaned = invoice_json.strip()

    # LLMs verpacken ihre Ausgabe manchmal in Markdown-Codeblöcke – wir
    # schneiden alles außerhalb der geschweiften Klammern weg.
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    # LLM-Ausgaben sind nicht immer gültiges JSON. Häufig enthalten sie
    # Kommentare oder überflüssige Kommata. Diese versuchen wir zu
    # entfernen, bevor ``json.loads`` aufgerufen wird. Die Regex für
    # Zeilenkommentare ignoriert Protokolle wie ``https://``.
    cleaned = re.sub(r"(?<!:)//.*", "", cleaned)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r",\s*(?=[}\]])", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc
    try:
        data.setdefault("items", [])
        invoice = InvoiceContext(**data)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc

    # Nach dem Parsen prüfen wir jede Rechnungsposition auf Schlüsselwörter,
    # die auf Reisekosten hindeuten. Zusätzlich normalisieren wir Positionen,
    # die fälschlicherweise als Währungsmenge interpretiert wurden.
    travel_keywords = ("anfahrt", "fahrtkosten", "kilometer")
    currency_units = {"euro", "eur", "€"}
    for item in invoice.items:
        desc = item.description.casefold()
        if item.category != "travel" and any(kw in desc for kw in travel_keywords):
            item.category = "travel"
        unit = (item.unit or "").strip().casefold()
        if unit in currency_units:
            value = max(item.quantity, item.unit_price)
            item.quantity = 1.0
            item.unit_price = value
            item.unit = "EUR"
    return invoice


def missing_invoice_fields(invoice: "InvoiceContext") -> list[str]:
    """Prüft auf Pflichtfelder und listet fehlende Angaben auf."""

    # Für eine gültige Rechnung benötigen wir mindestens
    # - den Kundennamen
    # - eine Beschreibung der Dienstleistung
    # - mindestens eine Rechnungsposition
    # - den Gesamtbetrag
    missing: list[str] = []
    if not invoice.customer.get("name"):
        missing.append("customer.name")
    if not invoice.service.get("description"):
        missing.append("service.description")
    if not invoice.items:
        missing.append("items")
    if invoice.amount.get("total") in (None, ""):
        missing.append("amount.total")
    return missing

"""Datenmodelle für Rechnungen und Hilfsfunktionen."""

from pydantic import BaseModel, ValidationError
from typing import Literal, Optional
from datetime import date
import json
import re


def normalize_address(address: str) -> str:
    """Wandelt '<Straße> in <PLZ> <Ort>' in '<Straße>, <PLZ> <Ort>' um."""
    match = re.match(
        r"^(?P<street>.+?)\s+in\s+(?P<zip>\d{5})\s+(?P<city>.+)$",
        address.strip(),
    )
    if match:
        street = match.group("street").strip()
        zip_code = match.group("zip")
        city = match.group("city").strip()
        return f"{street}, {zip_code} {city}"
    return address


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
    # Ursprüngliche Kategorie des LLMs, bevor Heuristiken eingreifen.
    original_category: Optional[str] = None
    # Quelle der finalen Kategorie ("llm" oder "heuristic").
    category_source: Optional[str] = None

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

    def add_item(self, item: InvoiceItem) -> None:
        """Fügt eine neue Rechnungsposition hinzu und berechnet Preise neu."""
        self.items.append(item)
        # Lokaler Import, um Zirkularimporte zu vermeiden
        from app.pricing import apply_pricing

        apply_pricing(self)

    def remove_item(self, index: int) -> InvoiceItem:
        """Entfernt eine Rechnungsposition und berechnet Preise neu."""
        removed = self.items.pop(index)
        from app.pricing import apply_pricing

        apply_pricing(self)
        return removed


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

    customer = data.get("customer")
    if isinstance(customer, dict):
        addr = customer.get("address")
        if isinstance(addr, str):
            customer["address"] = normalize_address(addr)

    travel_keywords = ("anfahrt", "fahrtkosten", "kilometer")
    currency_units = {"euro", "eur", "€"}
    labor_keywords = ("stund", "arbeitszeit", "handwerker")
    labor_units = {"h", "std", "stunde", "stunden"}

    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    data["items"] = raw_items

    for index, raw in enumerate(raw_items):
        if isinstance(raw, str):
            raw = {
                "description": raw,
                "quantity": 0,
                "unit": "",
                "unit_price": 0.0,
            }
            raw_items[index] = raw
        elif not isinstance(raw, dict):
            # Nicht interpretierbare Positionen werden übersprungen.
            continue

        desc = (raw.get("description") or "").casefold()
        unit = (raw.get("unit") or "").strip().casefold()
        cat = (raw.get("category") or "").casefold()

        if cat in {"material", "travel", "labor"}:
            normalised_category = cat
        else:
            normalised_category = None

        heuristic_category: str | None = None
        if any(kw in desc for kw in travel_keywords):
            heuristic_category = "travel"
        elif unit in labor_units or any(kw in desc for kw in labor_keywords):
            heuristic_category = "labor"
        elif not normalised_category:
            heuristic_category = "material"

        raw["original_category"] = normalised_category
        if heuristic_category and heuristic_category != normalised_category:
            raw["category"] = heuristic_category
            raw["category_source"] = "heuristic"
        else:
            raw["category"] = normalised_category or heuristic_category or "material"
            raw["category_source"] = "llm" if normalised_category else "heuristic"

        if unit in currency_units:
            value = max(raw.get("quantity", 0), raw.get("unit_price", 0))
            raw["quantity"] = 1.0
            raw["unit_price"] = value
            raw["unit"] = "EUR"

    try:
        invoice = InvoiceContext(**data)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc

    # Platzhalter ohne Beschreibung oder Preis entfernen. Wir behalten
    # Positionen mit Menge 0, sofern ein Preis angegeben wurde, da LLMs
    # Materialkosten häufig als Gesamtbetrag ohne Menge liefern.
    invoice.items = [
        item
        for item in invoice.items
        if item.description.strip() and (item.quantity > 0 or item.unit_price > 0)
    ]

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

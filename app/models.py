"""Datenmodelle für Rechnungen und Hilfsfunktionen."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    conint,
    field_validator,
)
from typing import Literal, Optional, TypeVar
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


def format_address(address: "Address | None") -> str:
    """Gibt eine formatierte Adresse für die Abrechnung zurück."""
    if not address:
        return ""
    parts = [address.street or "", address.postal_code or "", address.city or ""]
    street = parts[0].strip()
    city = " ".join(part for part in parts[1:] if part).strip()
    if street and city:
        return f"{street}, {city}"
    return street or city


class Address(BaseModel):
    """Strukturierte Adresse des Kunden."""

    model_config = ConfigDict(extra="forbid")

    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


class Customer(BaseModel):
    """Kundendaten für die Extraktion."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    address: Optional[Address] = None


class LineItem(BaseModel):
    """Extrahierte Rechnungspositionen für die LLM-Ausgabe."""

    model_config = ConfigDict(extra="forbid")

    description: str
    type: Literal["material", "travel", "labor"]
    role: Optional[Literal["meister", "geselle"]] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price_cents: Optional[conint(ge=0)] = None


class MaterialLineItem(LineItem):
    """Materialpositionen."""

    type: Literal["material"]


class LaborLineItem(LineItem):
    """Arbeitszeitpositionen."""

    type: Literal["labor"]


class TravelLineItem(LineItem):
    """Fahrtkostenpositionen."""

    type: Literal["travel"]


class ExtractionResult(BaseModel):
    """Strikt validierbares Extraktionsschema für LLM-Ausgaben."""

    model_config = ConfigDict(extra="forbid")

    customer: Optional[Customer] = None
    line_items: list[LineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence_per_field: Optional[dict[str, float]] = None

    @field_validator("confidence_per_field")
    @classmethod
    def _validate_confidence(cls, value: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if value is None:
            return value
        invalid = {key: val for key, val in value.items() if not (0.0 <= val <= 1.0)}
        if invalid:
            raise ValueError("confidence_per_field values must be between 0 and 1")
        return value


class CustomerPass(BaseModel):
    """Pass 1: Kunde & Adresse."""

    model_config = ConfigDict(extra="forbid")

    customer: Optional[Customer] = None
    notes: list[str] = Field(default_factory=list)
    confidence_per_field: Optional[dict[str, float]] = None


class MaterialPass(BaseModel):
    """Pass 2: Materialpositionen."""

    model_config = ConfigDict(extra="forbid")

    line_items: list[MaterialLineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence_per_field: Optional[dict[str, float]] = None


class LaborPass(BaseModel):
    """Pass 3: Arbeitszeitpositionen."""

    model_config = ConfigDict(extra="forbid")

    line_items: list[LaborLineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence_per_field: Optional[dict[str, float]] = None


class TravelPass(BaseModel):
    """Pass 4: Fahrtkosten und sonstige Positionen."""

    model_config = ConfigDict(extra="forbid")

    line_items: list[TravelLineItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence_per_field: Optional[dict[str, float]] = None


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

    cleaned = clean_json_text(invoice_json, error_label="empty invoice context")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc

    if isinstance(data, dict) and "line_items" in data:
        try:
            extraction = ExtractionResult.model_validate(data)
        except ValidationError as exc:
            raise ValueError("invalid extraction result") from exc
        missing = missing_extraction_fields(extraction)
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        return extraction_to_invoice_context(extraction)

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


TModel = TypeVar("TModel", bound=BaseModel)


def clean_json_text(raw: str, *, error_label: str = "empty json") -> str:
    """Bereitet JSON-Text aus LLM-Ausgaben auf."""
    if not raw or not raw.strip():
        raise ValueError(error_label)

    cleaned = raw.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    cleaned = re.sub(r"(?<!:)//.*", "", cleaned)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r",\s*(?=[}\]])", "", cleaned)
    return cleaned


def parse_model_json(raw_json: str, model_cls: type[TModel], *, error_label: str) -> TModel:
    """Parst LLM-JSON in ein Pydantic-Modell."""
    cleaned = clean_json_text(raw_json, error_label=error_label)
    try:
        return model_cls.model_validate_json(cleaned)
    except ValidationError as exc:
        raise ValueError(error_label) from exc


def parse_extraction_result(raw_json: str) -> ExtractionResult:
    """Validiert Extraktionsdaten gegen das ExtractionResult-Schema."""
    extraction = parse_model_json(
        raw_json, ExtractionResult, error_label="invalid extraction result"
    )
    missing = missing_extraction_fields(extraction)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    return extraction


def extraction_result_json_schema() -> dict:
    """Gibt das JSON-Schema für Extraktionsdaten zurück."""
    return ExtractionResult.model_json_schema()


def missing_extraction_fields(extraction: ExtractionResult) -> list[str]:
    """Ermittelt fehlende Pflichtfelder der Extraktion."""
    missing: list[str] = []
    if not extraction.line_items:
        missing.append("line_items")
    return missing


def extraction_to_invoice_context(extraction: ExtractionResult) -> InvoiceContext:
    """Wandelt Extraktionsdaten in das InvoiceContext-Format um."""
    customer = extraction.customer or Customer()
    customer_dict = {
        "name": customer.name or "",
        "address": format_address(customer.address),
    }
    items: list[InvoiceItem] = []
    for line_item in extraction.line_items:
        unit_price = (
            float(line_item.unit_price_cents) / 100.0
            if line_item.unit_price_cents is not None
            else 0.0
        )
        items.append(
            InvoiceItem(
                description=line_item.description,
                category=line_item.type,
                quantity=float(line_item.quantity or 0.0),
                unit=line_item.unit or "",
                unit_price=unit_price,
                worker_role=line_item.role,
                original_category=line_item.type,
                category_source="llm",
            )
        )
    return InvoiceContext(
        type="InvoiceContext",
        customer=customer_dict,
        service={"description": "", "materialIncluded": False},
        items=items,
        amount={"total": None, "currency": "EUR"},
    )


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

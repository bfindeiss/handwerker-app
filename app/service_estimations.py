from __future__ import annotations
from app.models import InvoiceItem
from app.service_templates import SERVICE_TEMPLATES


def estimate_labor_item(service_description: str) -> InvoiceItem:
    """Erzeugt eine Standard-Arbeitsposition basierend auf der Dienstleistung."""
    desc = (service_description or "").lower()
    hours = 8.0
    if "malen" in desc or "streichen" in desc:
        hours = 4.0
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


def estimate_invoice_items(service_description: str) -> list[InvoiceItem]:
    """Gibt eine Liste von Rechnungspositionen basierend auf Vorlagen zurück."""
    desc = (service_description or "").lower()
    key: str | None = None
    if "dusche" in desc:
        key = "dusche_einbauen"
    elif "fenster" in desc:
        key = "fenster_setzen"
    elif "laminat" in desc:
        key = "laminat_verlegen"
    elif "steckdose" in desc:
        key = "steckdose_installieren"

    if key and key in SERVICE_TEMPLATES:
        return [InvoiceItem(**item) for item in SERVICE_TEMPLATES[key]]

    return [estimate_labor_item(service_description)]

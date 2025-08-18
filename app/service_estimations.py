from __future__ import annotations
from app.models import InvoiceItem


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

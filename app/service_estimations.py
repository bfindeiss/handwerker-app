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
    """Schätzt passende Rechnungspositionen anhand der Dienstleistung.

    Die Funktion durchsucht die Beschreibung nach bekannten Schlüsselwörtern
    und wählt eine entsprechende Vorlage aus ``service_templates`` aus. Alle
    Einträge der gefundenen Vorlage werden in ``InvoiceItem``-Objekte
    umgewandelt und als Liste zurückgegeben. Wird kein Schlüsselwort
    gefunden, liefert die Funktion eine leere Liste.
    """

    desc = (service_description or "").lower()
    for keyword, template in SERVICE_TEMPLATES.items():
        if keyword in desc:
            return [InvoiceItem(**data) for data in template]
    return []

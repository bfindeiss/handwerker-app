from __future__ import annotations

"""Schätzt typische Arbeitspositionen anhand der Dienstleistungsbeschreibung."""

from app.models import InvoiceItem

# Einfache Zuordnung von Servicebeschreibungen zu geschätzten Stunden und Rollen
# Schlüssel werden in Kleinbuchstaben erwartet und per Teilstring-Abgleich genutzt.
LABOR_ESTIMATES: dict[str, tuple[float, str]] = {
    "einbau einer dusche": (8.0, "Geselle"),
    "montage eines waschbeckens": (4.0, "Geselle"),
}


def estimate_labor_item(service_description: str) -> InvoiceItem:
    """Liefert eine geschätzte Arbeitsposition für die Dienstleistung.

    Wird kein Mapping gefunden, wird eine konservative Standardannahme von
    einer Stunde für einen Gesellen genutzt.
    """
    description_lower = service_description.lower()
    for key, (hours, role) in LABOR_ESTIMATES.items():
        if key in description_lower:
            quantity, worker_role = hours, role
            break
    else:
        quantity, worker_role = 1.0, "Geselle"

    return InvoiceItem(
        description=f"Arbeitszeit {worker_role}",
        category="labor",
        quantity=quantity,
        unit="h",
        unit_price=0.0,
        worker_role=worker_role,
    )

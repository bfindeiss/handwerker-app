"""Hilfsfunktionen zur Bewertung von Rechnungspositionen."""

from __future__ import annotations

from datetime import date, datetime
from fastapi import HTTPException

from app.models import InvoiceContext, InvoiceItem
from app.settings import settings


def apply_pricing(invoice: InvoiceContext) -> None:
    """Ergänzt fehlende Preise und Basisangaben in einer Rechnung.

    - Setzt für bekannte Kategorien Standardpreise aus den Einstellungen.
    - Berechnet den Gesamtbetrag aus den Positionen.
    - Vergibt Rechnungsnummer und Datum, falls nicht vorhanden.
    - Wirft eine ``HTTPException``, wenn für eine Position kein Preis
      ermittelt werden kann.
    """

    for item in invoice.items:
        if not item.unit_price:
            _apply_item_price(item)

    invoice.amount["total"] = sum(i.total for i in invoice.items)

    if not invoice.invoice_number:
        invoice.invoice_number = f"INV-{datetime.utcnow():%Y%m%d%H%M%S}"
    if not invoice.issue_date:
        invoice.issue_date = date.today()


def _apply_item_price(item: InvoiceItem) -> None:
    """Weist einer Rechnungsposition einen Standardpreis zu."""
    if item.category == "travel":
        item.unit_price = settings.travel_rate_per_km
    elif item.category == "labor":
        role = (item.worker_role or "").lower()
        if "meister" in role:
            item.unit_price = settings.labor_rate_meister
        elif "gesell" in role:
            item.unit_price = settings.labor_rate_geselle
        else:
            item.unit_price = settings.labor_rate_default
    elif item.category == "material":
        if settings.material_rate_default is not None:
            item.unit_price = settings.material_rate_default
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Preis für Material '{item.description}' fehlt",
            )
    else:  # pragma: no cover - unbekannte Kategorie
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Kategorie '{item.category}'",
        )

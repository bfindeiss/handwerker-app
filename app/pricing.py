"""Hilfsfunktionen zur Bewertung von Rechnungspositionen."""

from __future__ import annotations

from datetime import date, datetime
from fastapi import HTTPException

from app.models import InvoiceContext, InvoiceItem
from app.settings import settings
from app.materials import lookup_material_price, register_material_price


def apply_pricing(invoice: InvoiceContext) -> None:
    """Ergänzt fehlende Preise und Basisangaben in einer Rechnung.

    - Setzt für bekannte Kategorien Standardpreise aus den Einstellungen.
    - Berechnet den Gesamtbetrag aus den Positionen.
    - Vergibt Rechnungsnummer und Datum, falls nicht vorhanden.
    - Wirft eine ``HTTPException``, wenn für eine Position kein Preis
      ermittelt werden kann.
    """

    for item in invoice.items:
        if item.category == "travel":
            if _price_missing(item):
                item.unit_price = settings.travel_rate_per_km
        elif _price_missing(item):
            try:
                _apply_item_price(item)
            except HTTPException:
                if item.quantity == 0:
                    item.unit_price = settings.material_rate_default or 0.0
                else:
                    raise
        elif item.category == "material":
            # Nutzerpreise für unbekannte Materialien für zukünftige Anfragen merken.
            if lookup_material_price(item.description) is None:
                register_material_price(item.description, item.unit_price)

    net = sum(i.total for i in invoice.items)
    tax = round(net * settings.vat_rate, 2)
    invoice.amount["net"] = net
    invoice.amount["tax"] = tax
    invoice.amount["total"] = net + tax

    if not invoice.invoice_number:
        invoice.invoice_number = f"INV-{datetime.utcnow():%Y%m%d%H%M%S}"
    if not invoice.issue_date:
        invoice.issue_date = date.today()


def _apply_item_price(item: InvoiceItem) -> None:
    """Weist einer Rechnungsposition einen Standardpreis zu."""
    if item.category == "labor":
        role = (item.worker_role or "").lower()
        if "meister" in role:
            item.unit_price = settings.labor_rate_meister
        elif "gesell" in role:
            item.unit_price = settings.labor_rate_geselle
        elif "azub" in role:
            item.unit_price = settings.labor_rate_default * 0.6
        else:
            item.unit_price = settings.labor_rate_default
    elif item.category == "material":
        price = lookup_material_price(item.description)
        if price is not None:
            item.unit_price = price
        elif settings.material_rate_default is not None:
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


def _price_missing(item: InvoiceItem) -> bool:
    """Erkennt, ob eine Position noch keinen nutzbaren Preis besitzt."""

    return item.unit_price in (None, 0.0)

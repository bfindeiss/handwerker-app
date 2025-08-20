import pytest
from datetime import date

from fastapi import HTTPException

from app.models import InvoiceContext, InvoiceItem
from app.pricing import apply_pricing
from app.settings import settings


def _base_invoice(items):
    return InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Max"},
        service={"description": "Arbeit"},
        items=items,
        amount={"net": 0, "tax": 0, "total": 0, "currency": "EUR"},
    )


def test_apply_pricing_defaults():
    invoice = _base_invoice([
        InvoiceItem(
            description="Fahrt",
            category="travel",
            quantity=10,
            unit="km",
            unit_price=0,
        ),
        InvoiceItem(
            description="Arbeit",
            category="labor",
            quantity=2,
            unit="h",
            unit_price=0,
            worker_role="Geselle",
        ),
    ])

    apply_pricing(invoice)

    assert invoice.items[0].unit_price == settings.travel_rate_per_km
    assert invoice.items[1].unit_price == settings.labor_rate_geselle
    assert invoice.amount["net"] == pytest.approx(
        invoice.items[0].total + invoice.items[1].total
    )
    assert invoice.amount["tax"] == pytest.approx(
        invoice.amount["net"] * settings.vat_rate
    )
    assert invoice.amount["total"] == pytest.approx(
        invoice.amount["net"] + invoice.amount["tax"]
    )
    assert invoice.invoice_number is not None
    assert invoice.issue_date == date.today()


def test_apply_pricing_travel_overrides_unit_price():
    """Provided travel prices are overridden by the configured rate."""
    invoice = _base_invoice([
        InvoiceItem(
            description="Fahrt",
            category="travel",
            quantity=5,
            unit="km",
            unit_price=123.45,
        )
    ])

    apply_pricing(invoice)

    assert invoice.items[0].unit_price == settings.travel_rate_per_km


def test_apply_pricing_material_missing():
    invoice = _base_invoice([
        InvoiceItem(
            description="Material",
            category="material",
            quantity=1,
            unit="stk",
            unit_price=0,
        )
    ])

    with pytest.raises(HTTPException):
        apply_pricing(invoice)


def test_material_lookup_and_vat():
    invoice = _base_invoice([
        InvoiceItem(
            description="Schraube",
            category="material",
            quantity=10,
            unit="stk",
            unit_price=0,
        )
    ])

    apply_pricing(invoice)

    assert invoice.items[0].unit_price == 0.10
    assert invoice.amount["tax"] == pytest.approx(invoice.amount["net"] * settings.vat_rate)


def test_repricing_after_item_changes():
    invoice = _base_invoice([
        InvoiceItem(
            description="Arbeit",
            category="labor",
            quantity=1,
            unit="h",
            unit_price=0,
            worker_role="Geselle",
        )
    ])

    apply_pricing(invoice)

    original = invoice.amount.copy()

    # Neuer Posten hinzufügen – Preise sollten automatisch neu berechnet werden
    invoice.add_item(
        InvoiceItem(
            description="Anfahrt",
            category="travel",
            quantity=5,
            unit="km",
            unit_price=0,
        )
    )

    assert invoice.amount["net"] == pytest.approx(sum(i.total for i in invoice.items))
    assert invoice.amount["tax"] == pytest.approx(invoice.amount["net"] * settings.vat_rate)
    assert invoice.amount["total"] == pytest.approx(
        invoice.amount["net"] + invoice.amount["tax"]
    )

    # Posten wieder entfernen – ursprüngliche Beträge sollten zurückkehren
    invoice.remove_item(1)
    assert invoice.amount["net"] == pytest.approx(original["net"])
    assert invoice.amount["tax"] == pytest.approx(original["tax"])
    assert invoice.amount["total"] == pytest.approx(original["total"])

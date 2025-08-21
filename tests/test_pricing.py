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


def test_apply_pricing_material_placeholder_uses_defaults():
    invoice = _base_invoice([
        InvoiceItem(
            description="Material",
            category="material",
            quantity=0,
            unit="stk",
            unit_price=0,
        ),
    ])

    apply_pricing(invoice)

    expected = settings.material_rate_default or 0
    assert invoice.items[0].unit_price == expected

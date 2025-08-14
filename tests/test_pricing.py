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
        amount={"total": 0, "currency": "EUR"},
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
    assert invoice.amount["total"] == invoice.items[0].total + invoice.items[1].total
    assert invoice.invoice_number is not None
    assert invoice.issue_date == date.today()


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

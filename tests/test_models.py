import json
import pytest

from app.models import (
    parse_invoice_context,
    InvoiceContext,
    InvoiceItem,
    missing_invoice_fields,
)


def test_parse_invoice_context_code_fence():
    raw = """```json
{
  "type": "InvoiceContext",
  "customer": {},
  "service": {},
  "items": [],
  "amount": {}
}
```"""
    invoice = parse_invoice_context(raw)
    assert invoice.type == "InvoiceContext"


def test_parse_invoice_context_invalid():
    with pytest.raises(ValueError):
        parse_invoice_context("not json")


def test_parse_invoice_context_missing_items():
    raw = '{"type": "InvoiceContext", "customer": {}, "service": {}, "amount": {}}'
    invoice = parse_invoice_context(raw)
    assert invoice.items == []


def test_parse_invoice_context_filters_empty_items():
    data = {
        "type": "InvoiceContext",
        "customer": {},
        "service": {},
        "items": [
            {
                "description": "",
                "category": "travel",
                "quantity": 0,
                "unit": "km",
                "unit_price": 1,
            },
            {
                "description": "Fenster-Material",
                "category": "material",
                "quantity": 1.0,
                "unit": "Stück",
                "unit_price": 100.0,
            },
        ],
        "amount": {},
    }
    invoice = parse_invoice_context(json.dumps(data))
    assert len(invoice.items) == 1
    assert invoice.items[0].description == "Fenster-Material"


def test_parse_invoice_context_with_comments_and_trailing_commas():
    raw = """
    {
      "type": "InvoiceContext", // Kommentar
      "customer": { "name": "Hans" },
      "service": { "description": "Malen" },
      "items": [
        {
          "description": "Holz", // Kommentar
          "category": "material",
          "quantity": 1,
          "unit": "stk",
          "unit_price": 5, // Kommentar
        },
      ],
      "amount": { "total": 5, "currency": "EUR" },
    }
    """
    invoice = parse_invoice_context(raw)
    assert invoice.items[0].description == "Holz"
    assert invoice.amount["total"] == 5


def test_parse_invoice_context_currency_unit_total():
    data = {
        "type": "InvoiceContext",
        "customer": {},
        "service": {},
        "items": [
            {
                "description": "Materialkosten",
                "category": "material",
                "quantity": 100.0,
                "unit": "Euro",
                "unit_price": 34.62,
            }
        ],
        "amount": {},
    }
    invoice = parse_invoice_context(json.dumps(data))
    item = invoice.items[0]
    assert item.quantity == 1.0
    assert item.unit_price == 100.0
    assert item.unit == "EUR"


def test_parse_invoice_context_keeps_zero_quantity_with_price():
    data = {
        "type": "InvoiceContext",
        "customer": {},
        "service": {},
        "items": [
            {
                "description": "Fenster-Material",
                "category": "material",
                "quantity": 0.0,
                "unit": "EUR",
                "unit_price": 300.0,
            }
        ],
        "amount": {},
    }
    invoice = parse_invoice_context(json.dumps(data))
    assert len(invoice.items) == 1
    item = invoice.items[0]
    assert item.quantity == 1.0
    assert item.unit_price == 300.0
    assert item.unit == "EUR"


@pytest.mark.parametrize(
    "description",
    ["Anfahrt zur Baustelle", "Fahrtkosten zur Baustelle", "Kilometerpauschale"],
)
def test_parse_invoice_context_corrects_travel_category(description: str):
    data = {
        "type": "InvoiceContext",
        "customer": {},
        "service": {},
        "items": [
            {
                "description": description,
                "category": "labor",
                "quantity": 1,
                "unit": "h",
                "unit_price": 10,
            }
        ],
        "amount": {},
    }
    invoice = parse_invoice_context(json.dumps(data))
    assert invoice.items[0].category == "travel"


def test_missing_invoice_fields():
    invoice = InvoiceContext(
        type="InvoiceContext", customer={}, service={}, items=[], amount={}
    )
    missing = missing_invoice_fields(invoice)
    assert missing == ["customer.name", "service.description", "items", "amount.total"]

    invoice.customer["name"] = "Hans"
    invoice.service["description"] = "Malen"
    invoice.items.append(
        InvoiceItem(
            description="Arbeitszeit Geselle",
            category="labor",
            quantity=1,
            unit="h",
            unit_price=40,
            worker_role="Geselle",
        )
    )
    invoice.amount["total"] = 40
    assert missing_invoice_fields(invoice) == []

import pytest

from app.models import parse_invoice_context, InvoiceContext, missing_invoice_fields


def test_parse_invoice_context_code_fence():
    raw = """```json\n{\n  \"type\": \"InvoiceContext\",\n  \"customer\": {},\n  \"service\": {},\n  \"amount\": {}\n}\n```"""
    invoice = parse_invoice_context(raw)
    assert invoice.type == "InvoiceContext"


def test_parse_invoice_context_invalid():
    with pytest.raises(ValueError):
        parse_invoice_context("not json")


def test_missing_invoice_fields():
    invoice = InvoiceContext(type="InvoiceContext", customer={}, service={}, amount={})
    missing = missing_invoice_fields(invoice)
    assert missing == ["customer.name", "service.description", "amount.total"]

    invoice.customer["name"] = "Hans"
    invoice.service["description"] = "Malen"
    invoice.amount["total"] = 10
    assert missing_invoice_fields(invoice) == []

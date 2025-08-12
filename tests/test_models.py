import pytest

from app.models import parse_invoice_context


def test_parse_invoice_context_code_fence():
    raw = """```json\n{\n  \"type\": \"InvoiceContext\",\n  \"customer\": {},\n  \"service\": {},\n  \"amount\": {}\n}\n```"""
    invoice = parse_invoice_context(raw)
    assert invoice.type == "InvoiceContext"


def test_parse_invoice_context_invalid():
    with pytest.raises(ValueError):
        parse_invoice_context("not json")

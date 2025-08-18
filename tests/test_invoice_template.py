from datetime import date

from app.invoice_template import format_invoice_lines
from app.models import InvoiceContext, InvoiceItem


def _sample_invoice() -> InvoiceContext:
    item = InvoiceItem(
        description="Beratungsleistung",
        category="labor",
        quantity=10,
        unit="h",
        unit_price=80.0,
    )
    return InvoiceContext(
        type="invoice",
        customer={
            "name": "Kunde AG",
            "address": "Kundenweg 10",
            "vat_id": "DE987654321",
        },
        service={"description": "Beratung"},
        items=[item],
        amount={
            "net": item.total,
            "tax": item.total * 0.19,
            "total": item.total * 1.19,
        },
        invoice_number="2024-00123",
        issue_date=date(2024, 6, 28),
    )


def test_format_invoice_contains_required_sections():
    invoice = _sample_invoice()
    lines = format_invoice_lines(invoice)
    text = "\n".join(lines)
    assert "Rechnung" in text
    assert "Rechnungsempfänger (Kunde)" in text
    assert "Rechnungsbetrag brutto" in text
    assert "Zahlungsinformationen" in text

from datetime import date

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import InvoiceContext, InvoiceItem
from app.pdf import generate_invoice_pdf
from app.settings import settings


def _sample_invoice() -> InvoiceContext:
    item = InvoiceItem(
        description="Testleistung",
        category="labor",
        quantity=1,
        unit="h",
        unit_price=100.0,
    )
    return InvoiceContext(
        type="invoice",
        customer={"name": "Kunde"},
        service={},
        items=[item],
        amount={
            "net": item.total,
            "tax": item.total * 0.19,
            "total": item.total * 1.19,
        },
        invoice_number="2024-0001",
        issue_date=date(2024, 1, 1),
    )


def test_generate_invoice_pdf_without_template(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "invoice_template_pdf", None)
    invoice = _sample_invoice()
    out_file = tmp_path / "invoice.pdf"
    generate_invoice_pdf(invoice, out_file)
    reader = PdfReader(str(out_file))
    text = reader.pages[0].extract_text()
    assert "Rechnung" in text


def test_generate_invoice_pdf_with_template(tmp_path, monkeypatch):
    template_path = tmp_path / "template.pdf"
    c = canvas.Canvas(str(template_path), pagesize=A4)
    c.drawString(50, 50, "TEMPLATE")
    c.showPage()
    c.save()

    monkeypatch.setattr(settings, "invoice_template_pdf", str(template_path))
    invoice = _sample_invoice()
    out_file = tmp_path / "invoice_template.pdf"
    generate_invoice_pdf(invoice, out_file)
    reader = PdfReader(str(out_file))
    text = reader.pages[0].extract_text()
    assert "Rechnung" in text
    assert "TEMPLATE" in text

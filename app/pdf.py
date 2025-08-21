"""Hilfsfunktionen zur Erzeugung einer einfachen E-Rechnungs-PDF."""

from pathlib import Path
from typing import Iterable
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import InvoiceContext
from app.invoice_template import format_invoice_lines
from app.settings import settings


def _write_lines(c: canvas.Canvas, lines: Iterable[str]) -> None:
    """Schreibt die gegebenen Zeilen in das PDF."""

    width, height = A4
    y = height - 50
    for line in lines:
        c.drawString(50, y, line)
        y -= 20


def generate_invoice_pdf(invoice: InvoiceContext, file_path: Path) -> None:
    """Erstellt eine einfache PDF-Datei mit Rechnungsdaten.

    Nutzt optional eine bestehende PDF-Vorlage als Hintergrund. Ist keine
    Vorlage hinterlegt, wird ein schlichtes Layout erzeugt.
    """

    lines = format_invoice_lines(invoice)

    if settings.invoice_template_pdf:
        # Overlay mit Rechnungsdaten erzeugen
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        _write_lines(c, lines)
        c.save()
        packet.seek(0)

        overlay = PdfReader(packet)
        template = PdfReader(settings.invoice_template_pdf)
        page = template.pages[0]
        page.merge_page(overlay.pages[0])

        writer = PdfWriter()
        writer.add_page(page)
        writer.add_metadata(
            {
                "/Title": "Rechnung",
                "/Author": "Handwerker App",
                "/Subject": "E-Rechnung",
            }
        )
        with open(file_path, "wb") as f:
            writer.write(f)
    else:
        c = canvas.Canvas(str(file_path), pagesize=A4)
        c.setTitle("Rechnung")
        c.setAuthor("Handwerker App")
        c.setSubject("E-Rechnung")
        _write_lines(c, lines)
        c.showPage()
        c.save()

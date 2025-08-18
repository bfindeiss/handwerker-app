"""Hilfsfunktionen zur Erzeugung einer einfachen E-Rechnungs-PDF."""

from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import InvoiceContext
from app.invoice_template import format_invoice_lines


def _write_lines(c: canvas.Canvas, lines: Iterable[str]) -> None:
    """Schreibt die gegebenen Zeilen in das PDF."""

    width, height = A4
    y = height - 50
    for line in lines:
        c.drawString(50, y, line)
        y -= 20


def generate_invoice_pdf(invoice: InvoiceContext, file_path: Path) -> None:
    """Erstellt eine einfache PDF-Datei mit Rechnungsdaten.

    Die erzeugte PDF enthält grundlegende Angaben zur Rechnung und kann als
    Ausgangspunkt für eine EN‑16931‑konforme E‑Rechnung dienen.
    """

    c = canvas.Canvas(str(file_path), pagesize=A4)
    c.setTitle("Rechnung")
    c.setAuthor("Handwerker App")
    c.setSubject("E-Rechnung")

    lines = format_invoice_lines(invoice)

    _write_lines(c, lines)
    c.showPage()
    c.save()

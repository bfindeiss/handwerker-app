"""Formatierung einer Rechnung als strukturierter Text."""

from __future__ import annotations

from typing import List

from app.models import InvoiceContext
from app.settings import settings


def format_invoice_lines(invoice: InvoiceContext) -> List[str]:
    """Erzeugt Textzeilen für eine vollständig ausgefüllte Rechnung."""

    vat_rate = int(settings.vat_rate * 100)
    net = invoice.amount.get("net") or sum(i.total for i in invoice.items)
    tax = invoice.amount.get("tax") or net * settings.vat_rate
    total = invoice.amount.get("total") or net + tax

    lines: List[str] = ["Rechnung", ""]
    lines.extend(
        [
            "1. Rechnungsersteller (Lieferant)",
            f"Name/Firma: {settings.supplier_name}",
            f"Adresse: {settings.supplier_address}",
            f"USt-IdNr.: {settings.supplier_vat_id}",
            f"Kontakt: {settings.supplier_contact}",
            "",
        ]
    )
    lines.extend(
        [
            "2. Rechnungsempfänger (Kunde)",
            f"Name/Firma: {invoice.customer.get('name', '')}",
            f"Adresse: {invoice.customer.get('address', '')}",
            f"USt-IdNr./Steuernummer: {invoice.customer.get('vat_id', '')}",
            "",
        ]
    )
    issue_date = invoice.issue_date.isoformat() if invoice.issue_date else ""
    service_date = invoice.service.get("date", "")
    reference = invoice.service.get("reference", "")
    lines.extend(
        [
            "3. Rechnungsdetails",
            f"Rechnungsnummer: {invoice.invoice_number or ''}",
            f"Rechnungsdatum: {issue_date}",
            f"Liefer-/Leistungsdatum: {service_date}",
            f"Bestellreferenz: {reference}",
            "",
        ]
    )
    lines.append("4. Rechnungspositionen")
    lines.append(
        "Pos. | Beschreibung | Menge | Einzelpreis (netto) | MwSt-Satz | Betrag (netto)"
    )
    for idx, item in enumerate(invoice.items, start=1):
        lines.append(
            f"{idx} | {item.description} | {item.quantity} {item.unit} | "
            f"{item.unit_price:.2f} € | {vat_rate}% | {item.total:.2f} €"
        )
    lines.extend(
        [
            "",
            f"Zwischensumme netto: {net:.2f} €",
            f"Umsatzsteuer {vat_rate}%: {tax:.2f} €",
            f"Rechnungsbetrag brutto: {total:.2f} €",
            "",
        ]
    )
    lines.extend(
        [
            "5. Zahlungsinformationen",
            f"Zahlungsbedingungen: {settings.payment_terms}",
            f"Bankverbindung: IBAN {settings.payment_iban}, BIC {settings.payment_bic}",
            f"Verwendungszweck: Rechnungsnummer {invoice.invoice_number or ''}",
            "",
        ]
    )
    lines.extend(
        [
            "6. Sonstige Pflichtangaben",
            "Hinweis auf steuerbefreite Umsätze (falls zutreffend)",
            "",
            "7. Elektronische Formatangaben",
            "Format: XRechnung Version 2.3",
            f"Dateiname: {invoice.invoice_number or 'rechnung'}.xml",
        ]
    )
    return lines

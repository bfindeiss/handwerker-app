"""Einfache XML-Ausgabe im XRechnung-ähnlichen Format."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

from app.models import InvoiceContext


def generate_xrechnung_xml(invoice: InvoiceContext, file_path: Path) -> None:
    """Schreibt eine stark vereinfachte XRechnung-XML.

    Die erzeugte Datei ist **nicht** vollständig EN-16931-konform, dient aber
    als Ausgangspunkt für weitere Erweiterungen.
    """

    root = Element("Invoice")
    SubElement(root, "InvoiceNumber").text = invoice.invoice_number or ""
    SubElement(root, "IssueDate").text = (
        invoice.issue_date.isoformat() if invoice.issue_date else ""
    )

    customer = SubElement(root, "Customer")
    SubElement(customer, "Name").text = invoice.customer.get("name", "")

    items_el = SubElement(root, "Items")
    for item in invoice.items:
        item_el = SubElement(items_el, "Item")
        SubElement(item_el, "Description").text = item.description
        SubElement(item_el, "Quantity").text = str(item.quantity)
        SubElement(item_el, "UnitPrice").text = f"{item.unit_price:.2f}"

    amounts = SubElement(root, "Amounts")
    SubElement(amounts, "Net").text = f"{invoice.amount.get('net', 0):.2f}"
    SubElement(amounts, "Tax").text = f"{invoice.amount.get('tax', 0):.2f}"
    SubElement(amounts, "Total").text = f"{invoice.amount.get('total', 0):.2f}"

    tree = ElementTree(root)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)

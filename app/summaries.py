"""Hilfsfunktionen für natürlichsprachliche Zusammenfassungen."""

from __future__ import annotations

from typing import Iterable

from app.models import InvoiceContext, InvoiceItem
from app.pricing import apply_pricing


def _format_quantity(value: float) -> str:
    """Formatiert Mengen mit maximal zwei Dezimalstellen."""

    if value is None:
        return "0"

    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value))}"

    return f"{value:.2f}".replace(".", ",")


def _format_money(value: float | None) -> str:
    """Gibt einen Geldbetrag im deutschen Format zurück."""

    if value is None:
        value = 0.0

    return f"{value:.2f}".replace(".", ",") + " Euro"


def _describe_item(index: int, item: InvoiceItem) -> str:
    """Erzeugt eine Beschreibung für eine Rechnungsposition."""

    quantity = _format_quantity(item.quantity)
    unit = item.unit or "Einheit"
    unit_for_quantity = f" {item.unit}" if item.unit else ""
    unit_price = _format_money(item.unit_price)
    total = _format_money(item.total)
    role = f" ({item.worker_role})" if item.worker_role else ""

    return (
        f"Position {index}: {item.description}{role} umfasst {quantity}{unit_for_quantity} "
        f"zu {unit_price} je {unit} mit einem Netto-Betrag von {total}."
    )


def _iter_item_descriptions(items: Iterable[InvoiceItem]) -> list[str]:
    """Formatiert alle Positionen einer Rechnung."""

    return [_describe_item(idx, item) for idx, item in enumerate(items, start=1)]


def build_invoice_summary(invoice: InvoiceContext) -> str:
    """Erstellt eine natürlichsprachliche Zusammenfassung einer Rechnung."""

    apply_pricing(invoice)

    customer_name = (invoice.customer.get("name") or "").strip()
    if customer_name:
        customer_sentence = f"Für den Kunden {customer_name} wurde die Leistung"
    else:
        customer_sentence = "Für den Kunden wurde die Leistung"

    service_description = (invoice.service.get("description") or "ohne Titel").strip()
    service_sentence = f" \"{service_description}\" erfasst."

    item_sentences = _iter_item_descriptions(invoice.items)

    net = invoice.amount.get("net") or 0.0
    tax = invoice.amount.get("tax") or 0.0
    total = invoice.amount.get("total") or net + tax

    totals = [
        f"Die Zwischensumme netto beträgt {_format_money(net)}.",
    ]
    if tax:
        totals.append(f"Die Umsatzsteuer liegt bei {_format_money(tax)}.")
    totals.append(
        f"Der Rechnungsbetrag brutto beläuft sich auf {_format_money(total)}."
    )

    sentences = [customer_sentence + service_sentence]
    sentences.extend(item_sentences)
    sentences.extend(totals)

    return " ".join(sentence.strip() for sentence in sentences if sentence)


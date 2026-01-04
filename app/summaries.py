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
        f"{index}: {item.description}{role} {quantity}{unit_for_quantity} à {unit_price} "
        f"({total})"
    )


def _iter_item_descriptions(items: Iterable[InvoiceItem]) -> list[str]:
    """Formatiert alle Positionen einer Rechnung."""

    return [_describe_item(idx, item) for idx, item in enumerate(items, start=1)]


def build_invoice_summary(invoice: InvoiceContext) -> str:
    """Erstellt eine natürlichsprachliche Zusammenfassung einer Rechnung."""

    apply_pricing(invoice)

    customer_name = (invoice.customer.get("name") or "").strip()
    if customer_name:
        customer_sentence = f"Kunde {customer_name}, Leistung"
    else:
        customer_sentence = "Kunde unbekannt, Leistung"

    service_description = (invoice.service.get("description") or "ohne Titel").strip()
    service_sentence = f"\"{service_description}\"."

    item_sentences = _iter_item_descriptions(invoice.items)

    net = invoice.amount.get("net") or 0.0
    tax = invoice.amount.get("tax") or 0.0
    total = invoice.amount.get("total") or net + tax

    if tax:
        totals_text = (
            f"Gesamt {_format_money(total)} (Netto {_format_money(net)}, MwSt {_format_money(tax)})."
        )
    else:
        totals_text = f"Gesamt {_format_money(total)}."

    item_text = (
        "Positionen: " + "; ".join(item_sentences) if item_sentences else "Keine Positionen"
    )
    summary = f"{customer_sentence} {service_sentence} {item_text}."
    summary = summary.strip()
    return f"{summary} {totals_text}".strip()

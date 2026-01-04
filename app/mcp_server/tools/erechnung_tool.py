"""E-invoice tool for the prepared MCP server (inactive)."""

from __future__ import annotations

from typing import Any


def generate_erechnung(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dummy e-invoice JSON payload."""

    payload = payload or {}
    invoice_id = payload.get("invoice_id", "INV-1000")

    return {
        "profile": "EN16931",
        "invoice_id": invoice_id,
        "issue_date": "2024-01-31",
        "supplier": {
            "name": "Beispiel GmbH",
            "vat_id": "DE123456789",
        },
        "customer": {
            "name": "Musterkunde GmbH",
            "vat_id": "DE999999999",
        },
        "totals": {
            "net": 175.0,
            "vat": 33.25,
            "gross": 208.25,
        },
    }

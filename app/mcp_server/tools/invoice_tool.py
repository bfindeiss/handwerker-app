"""Invoice tool for the prepared MCP server (inactive)."""

from __future__ import annotations

from typing import Any


def generate_invoice(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dummy invoice JSON structure.

    This is a placeholder implementation for the MCP "invoice" tool.
    """

    payload = payload or {}
    invoice_id = payload.get("invoice_id", "INV-1000")
    customer_id = payload.get("customer_id", "CUST-0001")

    return {
        "invoice_id": invoice_id,
        "customer_id": customer_id,
        "currency": "EUR",
        "line_items": [
            {
                "description": "Arbeitszeit (Geselle)",
                "quantity": 2,
                "unit_price": 50.0,
                "total": 100.0,
            },
            {
                "description": "Material (Beispiel)",
                "quantity": 1,
                "unit_price": 75.0,
                "total": 75.0,
            },
        ],
        "total_amount": 175.0,
    }

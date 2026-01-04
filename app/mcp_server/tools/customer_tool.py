"""Customer lookup tool for the prepared MCP server (inactive)."""

from __future__ import annotations

from typing import Any


def lookup_customer(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dummy customer record.

    This is a placeholder implementation for the MCP "customer lookup" tool.
    """

    payload = payload or {}
    customer_id = payload.get("customer_id", "CUST-0001")

    return {
        "customer_id": customer_id,
        "name": "Musterkunde GmbH",
        "address": "Beispielweg 5, 12345 Beispielstadt",
        "email": "rechnung@musterkunde.de",
        "phone": "+49 123 456789",
        "vat_id": "DE999999999",
    }

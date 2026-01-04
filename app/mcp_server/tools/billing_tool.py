"""Billing adapter tool for the prepared MCP server (inactive)."""

from __future__ import annotations

from typing import Any


def send_to_billing_adapter(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a success/error placeholder response for billing adapters."""

    payload = payload or {}
    simulate_error = payload.get("simulate_error", False)

    if simulate_error:
        return {
            "status": "error",
            "message": "Billing adapter placeholder error.",
            "reference": None,
        }

    return {
        "status": "success",
        "message": "Billing adapter placeholder success.",
        "reference": "BILLING-REF-123",
    }

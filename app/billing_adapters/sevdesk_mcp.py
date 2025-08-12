from __future__ import annotations

import httpx

from app.billing_adapter import BillingAdapter
from app.models import InvoiceContext
from app.settings import settings


class SevDeskMCPAdapter(BillingAdapter):
    """Send invoices to a SevDesk-compatible MCP server."""

    def __init__(self) -> None:
        self.endpoint = settings.mcp_endpoint or "http://localhost:8001"

    def send_invoice(self, invoice: InvoiceContext) -> dict:
        url = f"{self.endpoint.rstrip('/')}/invoice"
        response = httpx.post(url, json=invoice.model_dump(), timeout=10)
        response.raise_for_status()
        return response.json()

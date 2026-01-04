"""Prepared MCP server (inactive).

This module provides a minimal JSON-RPC server that follows the MCP tool
shape and is intentionally *not* wired into the main application flow.
Enable it explicitly via the ENABLE_MCP flag before using in production.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from jsonrpcserver import method, dispatch

from app.mcp_server.tools.billing_tool import send_to_billing_adapter
from app.mcp_server.tools.customer_tool import lookup_customer
from app.mcp_server.tools.erechnung_tool import generate_erechnung
from app.mcp_server.tools.invoice_tool import generate_invoice

logger = logging.getLogger(__name__)


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "invoice.generate": {
        "description": "Erzeugt eine Beispiel-Rechnung im internen JSON-Format.",
        "handler": generate_invoice,
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
        },
    },
    "customer.lookup": {
        "description": "Liefert Dummy-Kundenstammdaten.",
        "handler": lookup_customer,
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
            },
        },
    },
    "billing.adapter": {
        "description": "Platzhalter für einen Billing-Adapter.",
        "handler": send_to_billing_adapter,
        "input_schema": {
            "type": "object",
            "properties": {
                "simulate_error": {"type": "boolean"},
            },
        },
    },
    "erechnung.adapter": {
        "description": "Platzhalter für einen E-Rechnungs-Adapter.",
        "handler": generate_erechnung,
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
            },
        },
    },
}


def _format_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Format tool output similar to MCP tool responses."""

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "structured_result": payload,
        "is_error": False,
    }


@method(name="tools/list")
def list_tools() -> dict[str, Any]:
    """Return MCP-style tool metadata."""

    tools = []
    for name, meta in TOOL_REGISTRY.items():
        tools.append(
            {
                "name": name,
                "description": meta["description"],
                "input_schema": meta["input_schema"],
            }
        )
    return {"tools": tools}


@method(name="tools/call")
def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch a tool call to the prepared MCP registry."""

    arguments = arguments or {}
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return {
            "content": [{"type": "text", "text": f"Unbekanntes Tool: {name}"}],
            "structured_result": None,
            "is_error": True,
        }

    result = tool["handler"](arguments)
    return _format_tool_result(result)


class MCPRequestHandler(BaseHTTPRequestHandler):
    """Basic HTTP handler for JSON-RPC requests."""

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        content_length = int(self.headers.get("Content-Length", "0"))
        request_data = self.rfile.read(content_length).decode("utf-8")

        response = dispatch(request_data)
        if not response.wanted:
            self.send_response(204)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response.json.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        logger.debug("MCP server: %s", format % args)


def start_mcp_server(host: str = "127.0.0.1", port: int = 8001) -> HTTPServer:
    """Create an HTTP server instance for MCP JSON-RPC requests."""

    server = HTTPServer((host, port), MCPRequestHandler)
    return server


def run_mcp_server(host: str = "127.0.0.1", port: int = 8001) -> None:
    """Run the prepared MCP server.

    Note: This is intentionally not called from the main application. Enable
    the MCP flow explicitly when needed.
    """

    server = start_mcp_server(host=host, port=port)
    logger.info("Starting prepared MCP server at http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping prepared MCP server")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_mcp_server()

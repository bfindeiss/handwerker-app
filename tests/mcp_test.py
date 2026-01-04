"""Tests and examples for the prepared MCP server (inactive)."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

import httpx
from jsonrpcclient import parse, request

from app.mcp_server.mcp_server import start_mcp_server


@contextmanager
def run_server() -> Iterator[str]:
    server = start_mcp_server(host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _rpc_call(url: str, method: str, params: dict | None = None) -> dict:
    payload = request(method, params or {})
    response = httpx.post(url, json=payload, timeout=5)
    response.raise_for_status()
    parsed = list(parse(response.json()))
    return parsed[0].result


def test_mcp_list_tools() -> None:
    with run_server() as url:
        result = _rpc_call(url, "tools/list")
        tool_names = {tool["name"] for tool in result["tools"]}
        assert "invoice.generate" in tool_names
        assert "customer.lookup" in tool_names
        assert "billing.adapter" in tool_names
        assert "erechnung.adapter" in tool_names


def test_mcp_call_invoice_tool() -> None:
    with run_server() as url:
        result = _rpc_call(
            url,
            "tools/call",
            {"name": "invoice.generate", "arguments": {"invoice_id": "INV-42"}},
        )
        structured = result["structured_result"]
        assert structured["invoice_id"] == "INV-42"
        assert structured["total_amount"] == 175.0


if __name__ == "__main__":
    with run_server() as url:
        response = _rpc_call(url, "tools/list")
        print("Available tools:", response["tools"])

        invoice_response = _rpc_call(
            url,
            "tools/call",
            {"name": "invoice.generate", "arguments": {"invoice_id": "INV-1001"}},
        )
        print("Invoice response:", invoice_response)

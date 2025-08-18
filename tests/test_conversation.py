import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app  # noqa: E402
import app.conversation as conversation  # noqa: E402


def test_conversation_provisional_invoice(monkeypatch, tmp_data_dir):
    """Generates a provisional invoice even with sparse input."""
    conversation.SESSIONS.clear()
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "Einbau Dusche")

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {},
                "service": {"description": "Einbau einer Dusche"},
                "items": [
                    {
                        "description": "Duschset",
                        "category": "material",
                        "quantity": 1,
                        "unit": "stk",
                        "unit_price": 300,
                    }
                ],
                "amount": {},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": "abc"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    invoice = data["invoice"]
    assert invoice["customer"]["name"] == "Unbekannter Kunde"
    assert any(item["category"] == "labor" for item in invoice["items"])
    assert invoice["amount"]["total"] > 300
    assert "pdf_url" in data


def test_conversation_parse_error(monkeypatch, tmp_data_dir):
    """Even on parse errors a provisional invoice is returned."""
    conversation.SESSIONS.clear()
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "kaputt")
    monkeypatch.setattr(conversation, "extract_invoice_context", lambda t: "invalid")
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": "xyz"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert any(item["category"] == "labor" for item in data["invoice"]["items"])

import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app  # noqa: E402
import app.conversation as conversation  # noqa: E402


def test_conversation_followup(monkeypatch, tmp_data_dir):
    """Asks questions until all invoice data is provided."""
    conversation.SESSIONS.clear()

    transcripts = iter(["", "Hans Malen 100"])
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: next(transcripts))

    def fake_extract(text):
        data = {
            "type": "InvoiceContext",
            "customer": {},
            "service": {},
            "items": [],
            "amount": {},
        }
        if "Hans" in text:
            data["customer"] = {"name": "Hans"}
        if "Malen" in text:
            data["service"] = {"description": "Malen", "materialIncluded": True}
            data["items"].append(
                {
                    "description": "Arbeitszeit Geselle",
                    "category": "labor",
                    "quantity": 1,
                    "unit": "h",
                    "unit_price": 40,
                    "worker_role": "Geselle",
                }
            )
        if "100" in text:
            data["amount"] = {"total": 100.0, "currency": "EUR"}
        return json.dumps(data)

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    session_id = "abc"

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert "Wie heißt der Kunde" in data["question"]

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert "Rechnung" in data["message"]

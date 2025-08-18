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

    transcripts = iter(["", "Hans Malen"])
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
    assert "Gesamtbetrag" not in data["question"]

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert data["invoice"]["amount"]["total"] == 47.6
    assert "Rechnung" in data["message"]
    assert "47.6" in data["message"]


def test_conversation_parse_error_resets_session(monkeypatch, tmp_data_dir):
    """Session should restart on parse errors instead of looping."""
    conversation.SESSIONS.clear()

    transcripts = iter(["kaputt", "Hans Malen 100"])
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: next(transcripts))
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    session_id = "xyz"

    # Erste Anfrage: LLM liefert unverständliche Ausgabe
    monkeypatch.setattr(conversation, "extract_invoice_context", lambda t: "invalid")
    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert "konnte die angaben nicht verstehen" in data["question"].lower()

    # Zweite Anfrage: gültige Daten und erfolgreicher Abschluss
    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "Hans"},
                "service": {"description": "Malen", "materialIncluded": True},
                "items": [
                    {
                        "description": "Arbeitszeit Geselle",
                        "category": "labor",
                        "quantity": 1,
                        "unit": "h",
                        "unit_price": 40,
                        "worker_role": "Geselle",
                    }
                ],
                "amount": {"total": 100.0, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["invoice"]["customer"]["name"] == "Hans"

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
    conversation.INVOICE_STATE.clear()

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
    assert data["done"] is True
    invoice = data["invoice"]
    assert invoice["customer"]["name"] == "Unbekannter Kunde"
    assert any(item["category"] == "labor" for item in invoice["items"])
    assert invoice["amount"]["total"] > 50
    assert "pdf_url" in data
    assert "message" in data

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


def test_conversation_parse_error(monkeypatch, tmp_data_dir):
    """Even on parse errors a provisional invoice is returned."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
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
    assert data["done"] is True
    assert "Platzhalter" in data["message"]
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert any(item["category"] == "labor" for item in data["invoice"]["items"])


def test_conversation_parse_error_keeps_state(monkeypatch, tmp_data_dir):
    """Parse-Fehler sollen vorhandene Rechnungsdaten nicht verwerfen."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()

    transcripts = iter(["Hans Malen", "Nur eine Stunde"])
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: next(transcripts))

    def fake_extract(text):
        if "Nur eine Stunde" in text or "Nur 1 Stunde" in text:
            return "Nur eine Stunde"
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "Hans"},
                "service": {
                    "description": "Malen",
                    "materialIncluded": True,
                },
                "items": [
                    {
                        "description": "Arbeitszeit Geselle",
                        "category": "labor",
                        "quantity": 2,
                        "unit": "h",
                        "unit_price": 40,
                        "worker_role": "Geselle",
                    }
                ],
                "amount": {"total": 95.2, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    session_id = "parsekeep"

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert data["invoice"]["service"]["description"] == "Malen"
    assert session_id in conversation.INVOICE_STATE

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    invoice = data["invoice"]
    assert invoice["customer"]["name"] == "Hans"
    assert invoice["service"]["description"] == "Malen"


def test_conversation_store_company_name(monkeypatch, tmp_path):
    """Recognizes command to store company name in .env."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    env_file = tmp_path / ".env"
    monkeypatch.setattr(conversation, "ENV_PATH", env_file)
    monkeypatch.setattr(
        conversation,
        "transcribe_audio",
        lambda b: "Speichere meinen Firmennamen Beispiel GmbH",
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": "cfg"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert "gespeichert" in data["message"].lower()
    assert (
        env_file.read_text(encoding="utf-8").strip() == 'COMPANY_NAME="Beispiel GmbH"'
    )


def test_conversation_defaults(monkeypatch, tmp_data_dir):
    """Missing customer/service fields are filled with placeholders."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "Malen 100")


def test_conversation_estimates_labor_item(monkeypatch, tmp_data_dir):
    """Missing labor positions should be estimated automatically."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "Hans Dusche")

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {},
                "service": {},
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
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": "s"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert (
        data["invoice"]["service"]["description"]
        == "Dienstleistung nicht näher beschrieben"
    )


def test_conversation_keeps_context_on_correction(monkeypatch, tmp_data_dir):
    """Corrections with invalid parse keep prior context."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()

    transcripts = iter(["Huber Fenster", "Nur eine Stunde"])
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: next(transcripts))

    invoice_jsons = iter(
        [
            json.dumps(
                {
                    "type": "InvoiceContext",
                    "customer": {"name": "Huber"},
                    "service": {"description": "Fenster"},
                    "items": [
                        {
                            "description": "Arbeitszeit Geselle",
                            "category": "labor",
                            "quantity": 8,
                            "unit": "h",
                            "unit_price": 50,
                            "worker_role": "Geselle",
                        }
                    ],
                    "amount": {"total": 400.0, "currency": "EUR"},
                }
            ),
            "{invalid",
        ]
    )
    monkeypatch.setattr(
        conversation, "extract_invoice_context", lambda t: next(invoice_jsons)
    )
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    session_id = "corr"
    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert data["invoice"]["customer"]["name"] == "Huber"
    assert data["invoice"]["service"]["description"] == "Fenster"
    assert data["question"]
    assert "Wie heißt der Kunde" not in data["question"]

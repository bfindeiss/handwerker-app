import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app  # noqa: E402
import app.conversation as conversation  # noqa: E402
from app.models import InvoiceContext, InvoiceItem  # noqa: E402
from app.pricing import apply_pricing  # noqa: E402


def test_conversation_provisional_invoice(monkeypatch, tmp_data_dir):
    """Generates invoice summary first and finalizes after confirmation."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

    transcripts = iter(["Hans Malen", "Ja, passt."])
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
    assert data["status"] == "awaiting_confirmation"
    assert "Hans" in data["summary"]
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert data["invoice"]["amount"]["total"] == 47.6
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
    assert data["status"] == "confirmed"
    assert "Rechnung bestätigt" in data["message"]
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert data["invoice"]["amount"]["total"] == 47.6
    assert "vorläufige rechnung" in data["message"].lower()
    assert "47,60 euro" in data["message"].lower()


def test_conversation_correction_flow(monkeypatch, tmp_data_dir):
    """Allows corrections before confirmation and updates summary."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.PENDING_CONFIRMATION.clear()

    transcripts = iter(["Hans Malen zwei Stunden", "Nein, Menge drei", "Ja, passt."])
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: next(transcripts))

    def fake_extract(text):
        quantity = 2
        lowered = text.casefold()
        if "menge drei" in lowered or "3" in lowered or "drei" in lowered:
            quantity = 3
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "Hans"},
                "service": {"description": "Malen", "materialIncluded": True},
                "items": [
                    {
                        "description": "Arbeitszeit Geselle",
                        "category": "labor",
                        "quantity": quantity,
                        "unit": "h",
                        "unit_price": 40,
                        "worker_role": "Geselle",
                    }
                ],
                "amount": {"total": quantity * 47.6 / 2, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
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
    assert data["done"] is False
    assert data["status"] == "awaiting_confirmation"
    assert "2 h" in data["summary"].lower()

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert data["status"] == "awaiting_confirmation"
    assert "3 h" in data["summary"].lower()

    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is True
    assert data["status"] == "confirmed"
    assert "Rechnung bestätigt" in data["message"]


def test_conversation_parse_error(monkeypatch, tmp_data_dir):
    """Even on parse errors a provisional invoice is returned."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()
    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "kaputt 7 km")
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
    assert "Platzhalter" in data["message"]
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert any(item["category"] == "labor" for item in data["invoice"]["items"])
    assert any(item["category"] == "material" for item in data["invoice"]["items"])
    assert any(item["category"] == "travel" for item in data["invoice"]["items"])
    travel_item = next(
        item for item in data["invoice"]["items"] if item["category"] == "travel"
    )
    assert travel_item["quantity"] == 7.0


def test_conversation_parse_error_keeps_state(monkeypatch, tmp_data_dir):
    """Parse-Fehler sollen vorhandene Rechnungsdaten nicht verwerfen."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

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
    assert data["done"] is False
    assert data["status"] == "awaiting_confirmation"
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
    conversation.SESSION_STATUS.clear()
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
    conversation.PENDING_CONFIRMATION.clear()
    conversation.SESSION_STATUS.clear()

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "Malen 100")
    monkeypatch.setattr(
        conversation,
        "extract_invoice_context",
        lambda t: json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {},
                "service": {},
                "items": [],
                "amount": {},
            }
        ),
    )
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": "defaults"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert data.get("status") == "awaiting_confirmation"
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert (
        data["invoice"]["service"]["description"]
        == "Dienstleistung nicht näher beschrieben"
    )
    assert any(item["category"] == "labor" for item in data["invoice"]["items"])


def test_conversation_estimates_labor_item(monkeypatch, tmp_data_dir):
    """Missing labor positions should be estimated automatically."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

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
    assert data["done"] is False
    assert data["status"] == "awaiting_confirmation"
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert (
        data["invoice"]["service"]["description"]
        == "Dienstleistung nicht näher beschrieben"
    )


def test_conversation_extracts_hours_and_materials(monkeypatch, tmp_data_dir):
    """Transkriptangaben zu Stunden und Material werden übernommen."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

    transcript = (
        "Bitte erstelle eine Rechnung für den Einbau einer Tür und 2 Fenstern bei "
        "Hr. Hans Müller in der Rathausstr. 11 in 83727 Schliersee. "
        "Die Tür waren 500€ Materialkosten, die Fenster je 200€. Zusätzlich hatte ich "
        "noch 2 Meisterstunden und 4 Gesellenstunden, und 35km Anfahrtsweg."
    )

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: transcript)

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"address": "Rathausstr. 11 in Schliersee"},
                "service": {
                    "description": "Einbau einer Tür und 2 Fenstern",
                    "materialIncluded": False,
                },
                "items": [],
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
        data={"session_id": "extract"},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    invoice = payload["invoice"]

    assert invoice["customer"]["name"] == "Hans Müller"

    items = {(item["description"], item["category"]): item for item in invoice["items"]}

    door = items[("Tür", "material")]
    assert door["quantity"] == pytest.approx(1.0)
    assert door["unit_price"] == pytest.approx(500.0)

    windows = items[("Fenster", "material")]
    assert windows["quantity"] == pytest.approx(2.0)
    assert windows["unit_price"] == pytest.approx(200.0)

    meister = items[("Arbeitszeit Meister", "labor")]
    assert meister["quantity"] == pytest.approx(2.0)
    assert meister["unit_price"] == pytest.approx(70.0)

    geselle = items[("Arbeitszeit Geselle", "labor")]
    assert geselle["quantity"] == pytest.approx(4.0)
    assert geselle["unit_price"] == pytest.approx(50.0)

    travel = items[("Anfahrt", "travel")]
    assert travel["quantity"] == pytest.approx(35.0)
    assert travel["unit_price"] == pytest.approx(1.0)

    assert invoice["amount"]["net"] == pytest.approx(1275.0)
    assert invoice["amount"]["total"] == pytest.approx(1517.25)


def test_conversation_keeps_context_on_correction(monkeypatch, tmp_data_dir):
    """Corrections with invalid parse keep prior context."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

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
    assert data["done"] is False
    assert data.get("status") == "awaiting_confirmation"

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

def test_conversation_ignores_auto_customer_name(monkeypatch, tmp_data_dir):
    """LLM eingefügte Kundennamen werden verworfen."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "nur text")

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "John Doe"},
                "service": {"description": "Malen"},
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
                "amount": {"total": 40, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")


def test_conversation_clarification_needed_for_ambiguous_roles_and_material_sum(
    monkeypatch, tmp_data_dir
):
    """Asks structured clarification questions for roles and material sums."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "Max Muster"},
                "service": {"description": "Fensterreparatur", "materialIncluded": True},
                "items": [
                    {
                        "description": "Arbeitszeit",
                        "category": "labor",
                        "quantity": 2,
                        "unit": "h",
                        "unit_price": 0,
                        "worker_role": None,
                    },
                    {
                        "description": "Material",
                        "category": "material",
                        "quantity": 0,
                        "unit": "stk",
                        "unit_price": 0,
                    },
                ],
                "amount": {"total": 0, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation-text/",
        data={"session_id": "clarify", "text": "Meister und Geselle waren vor Ort."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification_needed"
    assert "Wie viele Meisterstunden?" in data["clarification_questions"]
    assert "Wie viele Gesellenstunden?" in data["clarification_questions"]
    assert "Wie hoch ist die Materialsumme?" in data["clarification_questions"]


def test_conversation_example_sentence_no_clarification(monkeypatch, tmp_data_dir):
    """Example sentence yields a normal confirmation flow without clarifications."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()
    conversation.PENDING_CONFIRMATION.clear()

    def fake_extract(text):
        return json.dumps(
            {
                "type": "InvoiceContext",
                "customer": {"name": "Max Muster"},
                "service": {"description": "Türeinbau", "materialIncluded": True},
                "items": [
                    {
                        "description": "Tür",
                        "category": "material",
                        "quantity": 1,
                        "unit": "Stück",
                        "unit_price": 300,
                    },
                    {
                        "description": "Arbeitszeit Meister",
                        "category": "labor",
                        "quantity": 2,
                        "unit": "h",
                        "unit_price": 60,
                        "worker_role": "Meister",
                    },
                    {
                        "description": "Arbeitszeit Geselle",
                        "category": "labor",
                        "quantity": 3,
                        "unit": "h",
                        "unit_price": 40,
                        "worker_role": "Geselle",
                    },
                    {
                        "description": "Anfahrt",
                        "category": "travel",
                        "quantity": 35,
                        "unit": "km",
                        "unit_price": 1.2,
                    },
                ],
                "amount": {"total": 0, "currency": "EUR"},
            }
        )

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    resp = client.post(
        "/conversation-text/",
        data={
            "session_id": "example",
            "text": (
                "Kunde Max Muster, Musterstraße 1 12345 Berlin. "
                "Material: Tür 1 Stück 300 Euro. Meister 2 Stunden, "
                "Geselle 3 Stunden, Anfahrt 35 km."
            ),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_confirmation"
    assert not data.get("clarification_questions")

def test_conversation_delete_position(monkeypatch):
    """Removes an invoice item when requested."""
    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.PENDING_CONFIRMATION.clear()
    conversation.SESSION_STATUS.clear()

    session_id = "del"
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde"},
        service={"description": "Service"},
        items=[
            InvoiceItem(
                description="Alt",
                category="labor",
                quantity=1,
                unit="h",
                unit_price=40,
                worker_role="Geselle",
            ),
            InvoiceItem(
                description="Neu",
                category="material",
                quantity=1,
                unit="stk",
                unit_price=10,
            ),
        ],
        amount={},
    )
    apply_pricing(invoice)
    conversation.INVOICE_STATE[session_id] = invoice

    monkeypatch.setattr(conversation, "transcribe_audio", lambda b: "Position 1 löschen")
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(
        conversation, "extract_invoice_context", lambda t: pytest.fail("should not be called")
    )

    client = TestClient(app)
    resp = client.post(
        "/conversation/",
        data={"session_id": session_id},
        files={"file": ("audio.wav", b"data")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice"]["customer"]["name"] == "Unbekannter Kunde"
    assert data["done"] is False
    assert "gelöscht" in data["message"].lower()

    invoice = conversation.INVOICE_STATE[session_id]
    assert len(invoice.items) == 1
    assert invoice.items[0].description == "Neu"
    assert invoice.amount["total"] == pytest.approx(11.9, abs=0.01)



def test_conversation_direct_price_correction(monkeypatch):
    """Recognizes corrections like 'Position 1 Preis ...'."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()

    session_id = "corr-price"
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde"},
        service={"description": "Service"},
        items=[
            InvoiceItem(
                description="Arbeitszeit",
                category="labor",
                quantity=1.0,
                unit="h",
                unit_price=40.0,
                worker_role="Geselle",
            )
        ],
        amount={},
    )
    apply_pricing(invoice)
    conversation.INVOICE_STATE[session_id] = invoice

    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(
        conversation,
        "extract_invoice_context",
        lambda t: pytest.fail("LLM merge should not run for direct corrections"),
    )

    client = TestClient(app)
    resp = client.post(
        "/conversation-text/",
        data={"session_id": session_id, "text": "Position 1 Preis ist 150 Euro"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert "preis" in data["message"].lower()
    assert "zusammen" in data["message"].lower()
    assert data["invoice"]["items"][0]["unit_price"] == 150.0
    assert data["session_status"] == "collecting"

    invoice_state = conversation.INVOICE_STATE[session_id]
    assert invoice_state.items[0].unit_price == 150.0
    assert conversation.SESSION_STATUS[session_id] == "collecting"


def test_conversation_direct_quantity_correction_without_field(monkeypatch):
    """Defaults to quantity when field is omitted in correction command."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()

    session_id = "corr-qty-default"
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde"},
        service={"description": "Service"},
        items=[
            InvoiceItem(
                description="Arbeitszeit",
                category="labor",
                quantity=2.0,
                unit="h",
                unit_price=40.0,
                worker_role="Geselle",
            )
        ],
        amount={},
    )
    apply_pricing(invoice)
    conversation.INVOICE_STATE[session_id] = invoice

    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(
        conversation,
        "extract_invoice_context",
        lambda t: pytest.fail("LLM merge should not run for direct corrections"),
    )

    client = TestClient(app)
    resp = client.post(
        "/conversation-text/",
        data={"session_id": session_id, "text": "Position 1 sind 4 Stunden"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice"]["items"][0]["quantity"] == 4.0
    message_lower = data["message"].lower()
    assert "menge in position 1 ist jetzt 4" in message_lower
    assert "ich fasse gleich neu zusammen" in message_lower
    assert conversation.INVOICE_STATE[session_id].items[0].quantity == pytest.approx(4.0)


def test_conversation_direct_customer_correction(monkeypatch):
    """Updates customer name via explicit correction command."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.SESSION_STATUS.clear()

    session_id = "corr-customer"
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={"name": ""},
        service={"description": "Service"},
        items=[
            InvoiceItem(
                description="Arbeitszeit",
                category="labor",
                quantity=1.0,
                unit="h",
                unit_price=40.0,
                worker_role="Geselle",
            )
        ],
        amount={},
    )
    apply_pricing(invoice)
    conversation.INVOICE_STATE[session_id] = invoice

    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(
        conversation,
        "extract_invoice_context",
        lambda t: pytest.fail("LLM merge should not run for direct corrections"),
    )

    client = TestClient(app)
    resp = client.post(
        "/conversation-text/",
        data={"session_id": session_id, "text": "Kunde ist Familie Müller."},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["done"] is False
    assert "kunde ist" in data["message"].lower()
    assert data["invoice"]["customer"]["name"] == "Familie Müller"
    assert data["session_status"] == "collecting"

    invoice_state = conversation.INVOICE_STATE[session_id]
    assert invoice_state.customer["name"] == "Familie Müller"
    assert conversation.SESSION_STATUS[session_id] == "collecting"

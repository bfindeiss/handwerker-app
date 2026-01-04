import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app import stt, llm_agent, conversation
from app import settings as app_settings


class DummyResponse:
    def __init__(self, text):
        self.text = text


class DummyChatResponse:
    class DummyChoice:
        class DummyMessage:
            def __init__(self, content):
                self.content = content

        def __init__(self, content):
            self.message = DummyChatResponse.DummyChoice.DummyMessage(content)

    def __init__(self, content):
        self.choices = [DummyChatResponse.DummyChoice(content)]


class DummyOpenAI:
    def __init__(self, result):
        if isinstance(result, list):
            self.results = result
        else:
            self.results = [result]
        self.index = 0
        self.calls = 0

    class Audio:
        def __init__(self, parent):
            self.parent = parent

        class Transcriptions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, **kwargs):
                return DummyResponse(self.parent.parent.results[0])

        @property
        def transcriptions(self):
            return DummyOpenAI.Audio.Transcriptions(self)

    class Chat:
        def __init__(self, parent):
            self.parent = parent

        class Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, **kwargs):
                self.parent.parent.calls += 1
                if self.parent.parent.index < len(self.parent.parent.results):
                    content = self.parent.parent.results[self.parent.parent.index]
                    self.parent.parent.index += 1
                else:
                    content = self.parent.parent.results[-1]
                return DummyChatResponse(content)

        @property
        def completions(self):
            return DummyOpenAI.Chat.Completions(self)

    @property
    def audio(self):
        return DummyOpenAI.Audio(self)

    @property
    def chat(self):
        return DummyOpenAI.Chat(self)


def test_end_to_end(monkeypatch, tmp_data_dir):
    """Full pipeline via /process-audio/ endpoint."""
    monkeypatch.setattr(stt.settings, "stt_provider", "openai")
    monkeypatch.setattr(stt.settings, "stt_model", "whisper-1")
    monkeypatch.setattr(stt, "OpenAI", lambda: DummyOpenAI("transcript"))

    dummy_json = [
        json.dumps({"customer": {"name": "Anna"}}),
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Fenster-Material",
                        "type": "material",
                        "quantity": 1.0,
                        "unit": "Stk",
                        "unit_price_cents": 10000,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Arbeitszeit Geselle",
                        "type": "labor",
                        "role": "geselle",
                        "quantity": 1.0,
                        "unit": "h",
                        "unit_price_cents": 5000,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "line_items": [
                    {
                        "description": "Anfahrt",
                        "type": "travel",
                        "quantity": 10.0,
                        "unit": "km",
                        "unit_price_cents": 100,
                    }
                ]
            }
        ),
    ]
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_agent.settings, "llm_model", "gpt-4o")
    dummy = DummyOpenAI(dummy_json)
    monkeypatch.setattr(llm_agent, "OpenAI", lambda: dummy)

    monkeypatch.setattr(app_settings.settings, "billing_adapter", None)

    client = TestClient(app)
    response = client.post("/process-audio/", files={"file": ("audio.wav", b"data")})
    assert response.status_code == 200
    data = response.json()
    assert data["invoice"]["customer"]["name"] == "Anna"
    assert data["invoice"]["items"][1]["worker_role"] == "geselle"
    assert Path(data["log_dir"]).exists()
    assert Path(data["pdf_path"]).exists()
    assert data["pdf_url"].endswith("invoice.pdf")


def test_conversation_flow_integration(monkeypatch, tmp_data_dir):
    """Conversation endpoint requires confirmation before finalizing."""

    conversation.SESSIONS.clear()
    conversation.INVOICE_STATE.clear()
    conversation.PENDING_CONFIRMATION.clear()

    def fake_extract(text):
        base = {
            "type": "InvoiceContext",
            "customer": {"name": "Anna"},
            "service": {"description": "Streichen", "materialIncluded": True},
            "items": [
                {
                    "description": "Arbeitszeit Geselle",
                    "category": "labor",
                    "quantity": 1,
                    "unit": "h",
                    "unit_price": 50.0,
                    "worker_role": "Geselle",
                }
            ],
            "amount": {"total": 59.5, "currency": "EUR"},
        }
        return json.dumps(base)

    monkeypatch.setattr(conversation, "extract_invoice_context", fake_extract)
    monkeypatch.setattr(conversation, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(
        conversation, "store_interaction", lambda a, t, i: str(tmp_data_dir)
    )
    monkeypatch.setattr(conversation, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    session_id = "integration"

    resp = client.post(
        "/conversation-text/",
        data={"session_id": session_id, "text": "Anna streichen"},
    )
    assert resp.status_code == 200
    first = resp.json()
    assert first["done"] is False
    assert first["status"] == "awaiting_confirmation"
    assert "Anna" in first["summary"]

    resp = client.post(
        "/conversation-text/",
        data={"session_id": session_id, "text": "Ja, passt."},
    )
    assert resp.status_code == 200
    second = resp.json()
    assert second["done"] is True
    assert second["status"] == "confirmed"
    assert "Rechnung bestätigt" in second["message"]

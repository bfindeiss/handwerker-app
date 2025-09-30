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
        self.result = result

    class Audio:
        def __init__(self, parent):
            self.parent = parent

        class Transcriptions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, **kwargs):
                return DummyResponse(self.parent.parent.result)

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
                return DummyChatResponse(self.parent.parent.result)

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

    dummy_json = json.dumps(
        {
            "type": "InvoiceContext",
            "customer": {"name": "Anna"},
            "service": {"description": "paint", "materialIncluded": True},
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
            "amount": {"total": 50.0, "currency": "EUR"},
        }
    )
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_agent.settings, "llm_model", "gpt-4o")
    monkeypatch.setattr(llm_agent, "OpenAI", lambda: DummyOpenAI(dummy_json))

    monkeypatch.setattr(app_settings.settings, "billing_adapter", None)

    client = TestClient(app)
    response = client.post("/process-audio/", files={"file": ("audio.wav", b"data")})
    assert response.status_code == 200
    data = response.json()
    assert data["invoice"]["customer"]["name"] == "Anna"
    assert data["invoice"]["items"][0]["worker_role"] == "Geselle"
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

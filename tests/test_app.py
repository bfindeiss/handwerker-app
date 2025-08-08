import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app.main as app_main
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app import transcriber, llm_agent, billing_adapter, persistence, tts, telephony
from app import settings as app_settings
from app.models import InvoiceContext

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



def test_transcribe_audio(monkeypatch):
    """Transcribes audio using OpenAI STT"""
    monkeypatch.setattr(transcriber.settings, "stt_provider", "openai")
    monkeypatch.setattr(transcriber.settings, "stt_model", "whisper-1")
    monkeypatch.setattr(transcriber, "OpenAI", lambda: DummyOpenAI("hallo"))
    result = transcriber.transcribe_audio(b"audio")
    assert result == "hallo"


def test_transcribe_audio_command(monkeypatch):
    """Transcribes audio using a command line STT backend"""
    monkeypatch.setattr(transcriber.settings, "stt_provider", "command")
    monkeypatch.setattr(transcriber.settings, "stt_model", "dummycmd")

    def fake_run(cmd, capture_output=True, text=True, check=True):
        class R:
            stdout = "hi\n"

        return R()

    monkeypatch.setattr(transcriber.subprocess, "run", fake_run)
    result = transcriber.transcribe_audio(b"audio")
    assert result == "hi"


def test_extract_invoice_context(monkeypatch):
    """Extracts invoice context from text via OpenAI LLM"""
    dummy_json = json.dumps({"type": "InvoiceContext"})
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_agent.settings, "llm_model", "gpt-4o")
    monkeypatch.setattr(llm_agent, "OpenAI", lambda: DummyOpenAI(dummy_json))
    result = llm_agent.extract_invoice_context("text")
    assert json.loads(result)["type"] == "InvoiceContext"


def test_extract_invoice_context_ollama(monkeypatch):
    """Extracts invoice context via Ollama LLM"""
    dummy_json = json.dumps({"type": "InvoiceContext"})
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm_agent.settings, "llm_model", "test")

    def fake_post(url, json=None, timeout=60):
        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"response": dummy_json}

        return Resp()

    monkeypatch.setattr(llm_agent.requests, "post", fake_post)
    result = llm_agent.extract_invoice_context("text")
    assert json.loads(result)["type"] == "InvoiceContext"


def test_extract_invoice_context_ollama_model_missing(monkeypatch):
    """Returns a helpful error when Ollama model is missing"""
    monkeypatch.setattr(llm_agent.settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm_agent.settings, "llm_model", "missing")

    class Resp:
        status_code = 404

        def json(self):
            return {"error": "model not found"}

    def fake_post(url, json=None, timeout=60):
        return Resp()

    monkeypatch.setattr(llm_agent.requests, "post", fake_post)
    with pytest.raises(RuntimeError) as exc:
        llm_agent.extract_invoice_context("text")
    assert "model not found" in str(exc.value)


def test_store_interaction(tmp_data_dir):
    """Stores audio, transcript and invoice files"""
    invoice = InvoiceContext(type="InvoiceContext", customer={}, service={}, amount={})
    session_dir = persistence.store_interaction(b"audio", "transcript", invoice)
    p = Path(session_dir)
    assert (p / "audio.wav").exists()
    assert (p / "transcript.txt").exists()
    assert (p / "invoice.json").exists()


def test_process_audio(monkeypatch, tmp_data_dir):
    """Processes audio upload end-to-end"""
    monkeypatch.setattr(transcriber, "transcribe_audio", lambda x: "transcript")
    monkeypatch.setattr(app_main, "transcribe_audio", lambda x: "transcript")
    dummy_json = json.dumps(
        {
            "type": "InvoiceContext",
            "customer": {"name": "Hans"},
            "service": {"description": "test", "materialIncluded": True},
            "amount": {"total": 100.0, "currency": "EUR"},
        }
    )
    monkeypatch.setattr(llm_agent, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(app_main, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(billing_adapter, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(app_main, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(persistence, "store_interaction", lambda a, t, i: "dir")
    monkeypatch.setattr(app_main, "store_interaction", lambda a, t, i: "dir")

    client = TestClient(app)
    response = client.post(
        "/process-audio/",
        files={"file": ("audio.wav", b"data")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "transcript"
    assert data["invoice"]["customer"]["name"] == "Hans"
    assert data["billing_result"] == {"ok": True}


def test_root_endpoint():
    """Returns service info on root endpoint"""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_text_to_speech(monkeypatch):
    """Converts text to speech using gTTS"""
    class DummyTTS:
        def __init__(self, text, lang="de"):
            self.text = text
            self.lang = lang

        def write_to_fp(self, fp):
            fp.write(b"mp3")

    monkeypatch.setattr(tts.settings, "tts_provider", "gtts")
    monkeypatch.setattr(tts, "gTTS", DummyTTS)
    result = tts.text_to_speech("hallo")
    assert result == b"mp3"


def test_text_to_speech_elevenlabs(monkeypatch):
    """Converts text using ElevenLabs"""

    monkeypatch.setattr(tts.settings, "tts_provider", "elevenlabs")
    monkeypatch.setattr(tts.settings, "elevenlabs_api_key", "k")

    class DummyClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.text_to_speech = self

        def convert(self, *args, **kwargs):
            return [b"mp3"]

    monkeypatch.setattr(tts, "ElevenLabs", DummyClient)
    result = tts.text_to_speech("hi")
    assert result == b"mp3"


def test_twilio_recording(monkeypatch, tmp_data_dir):
    """Processes a Twilio recording webhook"""
    monkeypatch.setattr(telephony, "download_recording", lambda url: b"audio")
    monkeypatch.setattr(transcriber, "transcribe_audio", lambda b: "transcript")
    monkeypatch.setattr(telephony, "transcribe_audio", lambda b: "transcript")
    dummy_json = json.dumps(
        {
            "type": "InvoiceContext",
            "customer": {"name": "Hans"},
            "service": {"description": "test", "materialIncluded": True},
            "amount": {"total": 100.0, "currency": "EUR"},
        }
    )
    monkeypatch.setattr(llm_agent, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(telephony, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(billing_adapter, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(telephony, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(persistence, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(telephony, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(tts, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(telephony, "text_to_speech", lambda t: b"mp3")

    client = TestClient(app)
    response = client.post(
        "/twilio/recording",
        data={"RecordingUrl": "http://example.com/audio"},
    )
    assert response.status_code == 200


def test_sipgate_recording(monkeypatch, tmp_data_dir):
    """Processes a sipgate recording webhook"""
    monkeypatch.setattr(app_settings.settings, "telephony_provider", "sipgate")
    import importlib
    telephony_mod = importlib.reload(telephony)

    monkeypatch.setattr(telephony_mod, "download_recording", lambda url: b"audio")
    monkeypatch.setattr(transcriber, "transcribe_audio", lambda b: "transcript")
    monkeypatch.setattr(telephony_mod, "transcribe_audio", lambda b: "transcript")
    dummy_json = json.dumps({
        "type": "InvoiceContext",
        "customer": {"name": "Hans"},
        "service": {"description": "test", "materialIncluded": True},
        "amount": {"total": 100.0, "currency": "EUR"},
    })
    monkeypatch.setattr(llm_agent, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(telephony_mod, "extract_invoice_context", lambda t: dummy_json)
    monkeypatch.setattr(billing_adapter, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(telephony_mod, "send_to_billing_system", lambda i: {"ok": True})
    monkeypatch.setattr(persistence, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(telephony_mod, "store_interaction", lambda a, t, i: str(tmp_data_dir))
    monkeypatch.setattr(tts, "text_to_speech", lambda t: b"mp3")
    monkeypatch.setattr(telephony_mod, "text_to_speech", lambda t: b"mp3")

    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(telephony_mod.router)
    client = TestClient(test_app)
    response = client.post(
        "/sipgate/recording",
        data={"recordingUrl": "http://example.com/audio"},
    )
    assert response.status_code == 200 or response.json().get("status") == "ok"
 

def test_sevdesk_mcp_adapter(monkeypatch):
    """Sends invoice to sevDesk via MCP"""
    import app.billing_adapters.sevdesk_mcp as sevdesk_mcp
    adapter = sevdesk_mcp.SevDeskMCPAdapter()
    called = {}

    def fake_post(url, json=None, timeout=10):
        called['url'] = url
        called['json'] = json
        class Resp:
            def raise_for_status(self):
                pass
            def json(self):
                return {"status": "ok"}
        return Resp()

    monkeypatch.setattr(sevdesk_mcp.requests, 'post', fake_post)
    invoice = InvoiceContext(type="InvoiceContext", customer={}, service={}, amount={})
    result = adapter.send_invoice(invoice)
    assert called['url'].endswith('/invoice')
    assert called['json']['type'] == 'InvoiceContext'
    assert result == {"status": "ok"}


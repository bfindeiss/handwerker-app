import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib
from fastapi.testclient import TestClient
import pytest

from app import settings as app_settings
from app import billing_adapter, telephony
from app import persistence
from app.models import InvoiceContext


def test_default_billing_adapter(monkeypatch):
    """Uses default adapter when none specified"""
    monkeypatch.setattr(app_settings.settings, "billing_adapter", None)
    importlib.reload(billing_adapter)
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Max"},
        service={},
        items=[],
        amount={},
    )
    result = billing_adapter.send_to_billing_system(invoice)
    assert result["status"] == "success"
    assert "Max" in result["message"]


def test_env_billing_adapter(monkeypatch):
    """Loads adapter from environment variable"""
    monkeypatch.setattr(app_settings.settings, "billing_adapter", "app.billing_adapters.simple:SimpleAdapter")
    importlib.reload(billing_adapter)
    adapter = billing_adapter.get_adapter()
    from app.billing_adapters.simple import SimpleAdapter
    assert isinstance(adapter, SimpleAdapter)


def test_invalid_billing_adapter(monkeypatch):
    """Raises error if adapter string invalid"""
    monkeypatch.setattr(app_settings.settings, "billing_adapter", "app.models:InvoiceContext")
    importlib.reload(billing_adapter)
    with pytest.raises(TypeError):
        billing_adapter.get_adapter()


def test_invalid_stt_provider(monkeypatch):
    """Rejects invalid STT provider configuration"""
    from app import transcriber
    monkeypatch.setattr(app_settings.settings, "stt_provider", "foo")
    importlib.reload(transcriber)
    with pytest.raises(ValueError):
        transcriber._select_provider()


def test_invalid_llm_provider(monkeypatch):
    """Rejects invalid LLM provider configuration"""
    from app import llm_agent
    monkeypatch.setattr(app_settings.settings, "llm_provider", "foo")
    importlib.reload(llm_agent)
    with pytest.raises(ValueError):
        llm_agent._select_provider()


def test_invalid_tts_provider(monkeypatch):
    """Rejects invalid TTS provider configuration"""
    from app import tts
    monkeypatch.setattr(app_settings.settings, "tts_provider", "foo")
    importlib.reload(tts)
    with pytest.raises(ValueError):
        tts._select_provider()


def test_twilio_voice_endpoint(monkeypatch):
    """Returns XML for Twilio voice webhooks"""
    monkeypatch.setattr(app_settings.settings, "telephony_provider", "twilio")
    importlib.reload(telephony)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(telephony.router)
    client = TestClient(app)
    response = client.post("/twilio/voice")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")


def test_sipgate_voice_endpoint(monkeypatch):
    """Returns configuration for sipgate voice"""
    monkeypatch.setattr(app_settings.settings, "telephony_provider", "sipgate")
    telephony_mod = importlib.reload(telephony)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(telephony_mod.router)
    client = TestClient(app)
    response = client.post("/sipgate/voice")
    assert response.status_code == 200
    assert response.json().get("record").endswith("/sipgate/recording")


def test_store_interaction_unique_dirs(monkeypatch, tmp_path):
    """Creates unique directories for each interaction"""
    from datetime import datetime
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)
    class DummyDT(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
    monkeypatch.setattr(persistence, "datetime", DummyDT)
    invoice = InvoiceContext(
        type="InvoiceContext",
        customer={},
        service={},
        items=[],
        amount={},
    )
    dir1 = persistence.store_interaction(b"a", "t", invoice)
    monkeypatch.setattr(DummyDT, "utcnow", classmethod(lambda cls: datetime(2023, 1, 1, 12, 0, 1)))
    dir2 = persistence.store_interaction(b"b", "t", invoice)
    assert dir1 != dir2


def test_whisper_requires_ffmpeg(monkeypatch):
    """Raises an error if ffmpeg is not installed for Whisper."""
    import importlib
    import shutil
    from app import transcriber

    monkeypatch.setattr(app_settings.settings, "stt_provider", "whisper")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError):
        importlib.reload(transcriber)
        transcriber._select_provider()


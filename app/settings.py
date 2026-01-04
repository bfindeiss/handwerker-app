from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Liest Konfiguration aus Umgebungsvariablen oder ``.env``."""

    # API-Schlüssel und Adapter-Optionen
    openai_api_key: SecretStr | None = None
    billing_adapter: str | None = None
    mcp_endpoint: str | None = None

    # Vorgabewerte für KI- und STT-Backends
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    # Request timeout for Ollama interactions (seconds, minimum 300s)
    ollama_timeout: float = 300.0
    stt_provider: str = "openai"
    stt_model: str = "whisper-1"
    stt_prompt: str | None = None
    stt_language: str = "de"
    # Bild-zu-Text-Konvertierung
    ocr_provider: str = "tesseract"

    # Telefonie und Sprachausgabe
    telephony_provider: str = "twilio"
    tts_provider: str = "gtts"
    elevenlabs_api_key: SecretStr | None = None
    enable_manual_tts: bool = True

    # Standardpreise für Positionen, damit Rechnungen sinnvolle Beträge
    # enthalten, selbst wenn keine expliziten Angaben gemacht werden.
    travel_rate_per_km: float = 1.0
    labor_rate_geselle: float = 50.0
    labor_rate_meister: float = 70.0
    labor_rate_default: float = 60.0
    material_rate_default: float | None = None
    # Umsatzsteuersatz (z. B. 0.19 für 19 % MwSt.)
    vat_rate: float = 0.19

    # Angaben zum Rechnungsersteller
    supplier_name: str = "Beispiel GmbH"
    supplier_address: str = "Musterstraße 1, 12345 Musterstadt"
    supplier_vat_id: str = "DE123456789"
    supplier_contact: str = "info@beispiel.de, Tel. +49 123 456789"

    # Zahlungsinformationen
    payment_terms: str = "Zahlbar innerhalb von 30 Tagen ohne Abzug"
    payment_iban: str = "DE12 3456 7890 1234 5678 90"
    payment_bic: str = "ABCDDEFFXXX"

    # Optionale PDF-Vorlage für Rechnungen
    invoice_template_pdf: str | None = None

    # Optionaler Pfad zu einer externen Materialpreisdatei (JSON)
    material_prices_path: str | None = None

    # Verhalten beim Start, falls das LLM nicht erreichbar ist
    fail_on_llm_unavailable: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

"""Wählt je nach Konfiguration das passende Telefonie-Modul aus."""

from typing import Dict

from app.settings import settings

if settings.telephony_provider == "sipgate":
    # Nur die benötigten Symbole aus dem jeweiligen Modul importieren.
    from .sipgate import router, download_recording  # type: ignore

    # Sipgate benötigt keine Sitzungsverwaltung, daher ein leeres Dict.
    SESSIONS: Dict[str, str] = {}
else:  # default to twilio
    from .twilio import router, download_recording, SESSIONS  # type: ignore

__all__ = ["router", "download_recording", "SESSIONS"]

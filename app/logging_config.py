import logging
import re
from pathlib import Path


def mask_pii(text: str | None) -> str | None:
    """Maskiert einfache personenbezogene Daten in Log-Ausgaben."""
    if not text:
        return text
    # Sehr einfache Maskierung: Zahlen durch X ersetzen und E-Mails anonymisieren.
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    return re.sub(r"\d", "X", text)


def configure_logging() -> None:
    """Setzt ein Logging-Format und schreibt Debug in eine separate Datei."""
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "debug.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root.handlers = [console, file_handler]

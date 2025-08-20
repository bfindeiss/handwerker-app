from pathlib import Path
from datetime import datetime
import json
from app.models import InvoiceContext
from app.pdf import generate_invoice_pdf
from app.xrechnung import generate_xrechnung_xml

DATA_DIR = Path("data")
# Alle Sitzungen werden in diesem Verzeichnis abgelegt.
DATA_DIR.mkdir(exist_ok=True)


def store_interaction(
    audio: bytes, transcript: list[dict[str, str]] | str, invoice: InvoiceContext
) -> str:
    """Speichert alle Artefakte einer Sitzung unter ``data/<timestamp>/``."""

    # Ein ISO-Zeitstempel dient als eindeutiger Ordnername.
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    session_dir = DATA_DIR / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)

    # Transcript in strukturierter Form sichern
    if isinstance(transcript, str):
        messages = [{"role": "user", "content": transcript}]
    else:
        messages = transcript
    (session_dir / "transcript.json").write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    (session_dir / "transcript.txt").write_text(text, encoding="utf-8")

    # Rohdaten persistieren
    (session_dir / "audio.wav").write_bytes(audio)
    (session_dir / "invoice.json").write_text(
        json.dumps(invoice.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generate_invoice_pdf(invoice, session_dir / "invoice.pdf")
    generate_xrechnung_xml(invoice, session_dir / "invoice.xml")
    return str(session_dir)

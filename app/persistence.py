from pathlib import Path
from datetime import datetime
import json
from app.models import InvoiceContext

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def store_interaction(audio: bytes, transcript: str, invoice: InvoiceContext) -> str:
    """Persistiert Audio, Transkript und Rechnung in einem Zeitstempelordner."""
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    session_dir = DATA_DIR / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "audio.wav").write_bytes(audio)
    (session_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
    (session_dir / "invoice.json").write_text(json.dumps(invoice.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(session_dir)

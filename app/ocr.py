from __future__ import annotations

"""Simple OCR helper utility."""

import os
import subprocess
import tempfile
from pathlib import Path

from app.settings import settings


def extract_text(image_bytes: bytes) -> str:
    """Extracts text from image bytes using the configured provider."""
    provider = settings.ocr_provider
    if provider == "tesseract":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(image_bytes)
            tmp.flush()
            base = tmp.name
        out_base = base + "_out"
        try:
            subprocess.run(
                ["tesseract", base, out_base],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            text = Path(out_base + ".txt").read_text(encoding="utf-8")
            return text.strip()
        finally:
            os.unlink(base)
            txt_path = out_base + ".txt"
            if os.path.exists(txt_path):
                os.unlink(txt_path)
    raise ValueError(f"Unsupported OCR_PROVIDER {provider}")

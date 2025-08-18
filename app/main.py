import logging
from pathlib import Path
import time

from fastapi import File, HTTPException, UploadFile, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Die eigentliche Geschäftslogik steckt in diesen Hilfsmodulen. Wir holen sie
# hier zusammen, damit die FastAPI-Endpunkte schlank bleiben.
from app.billing_adapter import send_to_billing_system
from app.llm_agent import check_llm_backend, extract_invoice_context
from app.models import parse_invoice_context
from app.pricing import apply_pricing
from app.persistence import store_interaction
from app.settings import settings
from app.telephony import router as telephony_router
from app.conversation import router as conversation_router
from app.transcriber import transcribe_audio
from app.logging_config import configure_logging

# Einmalig beim Import die Standard-Logging-Konfiguration anwenden.
configure_logging()
logger = logging.getLogger(__name__)

# Globale FastAPI-App anlegen und statische Dateien sowie Telefonie-Routen
# registrieren.
app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Sitzungsartefakte (z. B. generierte PDFs) unter /data verfügbar machen.
app.mount("/data", StaticFiles(directory="data"), name="data")
app.include_router(telephony_router)
app.include_router(conversation_router)


@app.on_event("startup")
def _check_llm_backend() -> None:
    """Prüft beim Start, ob das konfigurierte LLM erreichbar ist."""
    if check_llm_backend():
        logger.info("LLM backend reachable")
        return
    # Der Dienst antwortet nicht – dem Nutzer einen Hinweis geben und je nach
    # Einstellung den Start abbrechen.
    msg = (
        "LLM backend unreachable. "
        "Consider switching to a fallback provider or set "
        "FAIL_ON_LLM_UNAVAILABLE=1 to abort startup."
    )
    if settings.fail_on_llm_unavailable:
        raise RuntimeError(msg)
    logger.warning(msg)


@app.get("/")
def read_root():
    """Simple health/info endpoint for the API root."""
    return {
        "message": "Handwerker Sprachassistent läuft",
        "usage": "POST audio file to /process-audio/",
    }


@app.get("/web")
def web_interface():
    """Serve unified HTML interface for recording and uploading audio."""
    return FileResponse("app/static/eunoia.html")


@app.post("/process-audio/")
async def process_audio(file: UploadFile = File(...)):
    """Hauptendpunkt: nimmt Audio entgegen und liefert Rechnungsdaten zurück."""
    start_total = time.perf_counter()
    success = False
    try:
        # 1) Audiodatei in den Arbeitsspeicher laden.
        audio_bytes = await file.read()

        # 2) Mithilfe des konfigurierten Speech‑to‑Text‑Backends in Text umwandeln.
        start = time.perf_counter()
        transcript = transcribe_audio(audio_bytes)
        transcription_duration = time.perf_counter() - start
        logger.info("Transcription took %.3f s", transcription_duration)
        logger.debug("Transcript: %s", transcript)

        # 3) Das Transkript an ein LLM schicken, das daraus JSON mit
        #    Rechnungsinformationen erzeugt.
        start = time.perf_counter()
        try:
            invoice_json = extract_invoice_context(transcript)
            logger.debug("LLM raw response: %s", invoice_json)
        except HTTPException as exc:
            logger.exception("LLM backend failure: %s", exc.detail)
            raise
        finally:
            llm_duration = time.perf_counter() - start
            logger.info("LLM call took %.3f s", llm_duration)

        # 4) JSON in das stark typisierte ``InvoiceContext``-Modell überführen.
        try:
            invoice = parse_invoice_context(invoice_json)
        except ValueError as exc:
            logger.exception(
                "Failed to parse invoice context: %s. Transcript: %s, Raw response: %s",
                exc,
                transcript,
                invoice_json,
            )
            raise HTTPException(status_code=502, detail=str(exc))

        # 5) Fehlende Preise ergänzen und Basisangaben setzen.
        apply_pricing(invoice)

        # 6) Rechnung an das externe System senden und alles lokal protokollieren.
        start = time.perf_counter()
        result = send_to_billing_system(invoice)
        billing_duration = time.perf_counter() - start
        logger.info("Invoice creation took %.3f s", billing_duration)
        log_dir = store_interaction(audio_bytes, transcript, invoice)
        logger.info("Processed audio successfully: log_dir=%s", log_dir)
        success = True

        pdf_path = str(Path(log_dir) / "invoice.pdf")
        pdf_url = "/" + pdf_path.replace("\\", "/")

        # 7) Die aufbereiteten Daten an den Aufrufer zurückgeben.
        return {
            "transcript": transcript,
            "invoice": invoice.model_dump(mode="json"),
            "billing_result": result,
            "log_dir": log_dir,
            "pdf_path": pdf_path,
            "pdf_url": pdf_url,
        }
    finally:
        total_duration = time.perf_counter() - start_total
        logger.info(
            "Total processing %s in %.3f s",
            "succeeded" if success else "failed",
            total_duration,
        )

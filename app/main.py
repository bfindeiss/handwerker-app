from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.transcriber import transcribe_audio
from app.llm_agent import extract_invoice_context
from app.billing_adapter import send_to_billing_system
from app.persistence import store_interaction
from app.models import parse_invoice_context
from app.telephony import router as telephony_router

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(telephony_router)


@app.get("/")
def read_root():
    """Simple health/info endpoint for the API root."""
    return {
        "message": "Handwerker Sprachassistent läuft",
        "usage": "POST audio file to /process-audio/",
    }


@app.get("/web")
def web_interface():
    """Serve simple HTML interface for recording and uploading audio."""
    return FileResponse("app/static/index.html")

@app.post("/process-audio/")
async def process_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    transcript = transcribe_audio(audio_bytes)
    invoice_json = extract_invoice_context(transcript)
    try:
        invoice = parse_invoice_context(invoice_json)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    result = send_to_billing_system(invoice)
    log_dir = store_interaction(audio_bytes, transcript, invoice)
    return {
        "transcript": transcript,
        "invoice": invoice.model_dump(),
        "billing_result": result,
        "log_dir": log_dir,
    }


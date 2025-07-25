from fastapi import FastAPI, UploadFile, File
from app.transcriber import transcribe_audio
from app.llm_agent import extract_invoice_context
from app.billing_adapter import send_to_billing_system
from app.persistence import store_interaction
from app.models import InvoiceContext
from app.telephony import router as telephony_router
import json

app = FastAPI()
app.include_router(telephony_router)

@app.post("/process-audio/")
async def process_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    transcript = transcribe_audio(audio_bytes)
    invoice_json = extract_invoice_context(transcript)
    invoice = InvoiceContext(**json.loads(invoice_json))
    result = send_to_billing_system(invoice)
    log_dir = store_interaction(audio_bytes, transcript, invoice)
    return {
        "transcript": transcript,
        "invoice": invoice.dict(),
        "billing_result": result,
        "log_dir": log_dir,
    }


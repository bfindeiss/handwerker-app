from fastapi import FastAPI, UploadFile, File
from app.transcriber import transcribe_audio
from app.llm_agent import extract_invoice_context
from app.billing_adapter import send_to_billing_system
from app.models import InvoiceContext
import json

app = FastAPI()

@app.post("/process-audio/")
async def process_audio(file: UploadFile = File(...)):
    transcript = transcribe_audio(await file.read())
    invoice_json = extract_invoice_context(transcript)
    invoice = InvoiceContext(**json.loads(invoice_json))
    result = send_to_billing_system(invoice)
    return {"transcript": transcript, "invoice": invoice.dict(), "billing_result": result}
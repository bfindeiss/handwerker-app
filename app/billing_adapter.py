from app.models import InvoiceContext

def send_to_billing_system(invoice: InvoiceContext) -> dict:
    return {"status": "success", "message": f"Rechnung für {invoice.customer['name']} verarbeitet."}
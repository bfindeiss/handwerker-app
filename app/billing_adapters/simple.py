from app.billing_adapter import BillingAdapter
from app.models import InvoiceContext

class SimpleAdapter(BillingAdapter):
    """Example adapter that just echoes the invoice."""
    def send_invoice(self, invoice: InvoiceContext) -> dict:
        return {
            "status": "success",
            "message": f"Local invoice for {invoice.customer.get('name')} stored."
        }

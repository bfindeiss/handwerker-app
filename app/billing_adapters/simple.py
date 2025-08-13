"""Sehr einfacher Rechnungsadapter."""

from app.billing_adapter import BillingAdapter
from app.models import InvoiceContext


class SimpleAdapter(BillingAdapter):
    """Beispieladapter: bestätigt lediglich den Empfang der Rechnung."""

    def send_invoice(self, invoice: InvoiceContext) -> dict:
        """Simuliert das Versenden einer Rechnung.

        In einer echten Integration würde hier eine API des
        Buchhaltungssystems aufgerufen. Wir liefern nur eine kurze
        Bestätigung zurück.
        """

        return {
            "status": "success",
            "message": f"Local invoice for {invoice.customer.get('name')} stored.",
        }


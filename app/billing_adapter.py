from __future__ import annotations
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Optional

from app.models import InvoiceContext
from app.settings import settings


class BillingAdapter(ABC):
    """Basisklasse für alle Rechnungs-Schnittstellen."""

    @abstractmethod
    def send_invoice(self, invoice: InvoiceContext) -> dict:
        """Send the given invoice to an external billing system."""
        raise NotImplementedError


class DummyAdapter(BillingAdapter):
    """Einfache Rückfalllösung, die nur einen Erfolgsstatus liefert."""

    def send_invoice(self, invoice: InvoiceContext) -> dict:
        return {
            "status": "success",
            "message": f"Rechnung für {invoice.customer.get('name')} verarbeitet."
        }


def _load_adapter(path: Optional[str]) -> BillingAdapter:
    """Dynamisch eine Adapter-Klasse aus ``module:Class`` laden."""
    if not path:
        # Keine Konfiguration vorhanden → Dummy verwenden.
        return DummyAdapter()
    module_name, class_name = path.split(":")
    module = import_module(module_name)
    adapter_cls = getattr(module, class_name)
    if not issubclass(adapter_cls, BillingAdapter):
        raise TypeError("Adapter must inherit from BillingAdapter")
    return adapter_cls()


_adapter: Optional[BillingAdapter] = None


def get_adapter() -> BillingAdapter:
    """Gibt den einmalig initialisierten Adapter zurück."""
    global _adapter
    if _adapter is None:
        _adapter = _load_adapter(settings.billing_adapter)
    return _adapter


def send_to_billing_system(invoice: InvoiceContext) -> dict:
    """Hilfsfunktion für den Rest des Codes, der keine Adapterdetails kennt."""
    adapter = get_adapter()
    return adapter.send_invoice(invoice)

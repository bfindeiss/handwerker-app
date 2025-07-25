from __future__ import annotations
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Optional

from app.models import InvoiceContext
from app.settings import settings


class BillingAdapter(ABC):
    """Interface for all billing adapters."""

    @abstractmethod
    def send_invoice(self, invoice: InvoiceContext) -> dict:
        """Send the given invoice to an external billing system."""
        raise NotImplementedError


class DummyAdapter(BillingAdapter):
    """Fallback adapter used when no other adapter is configured."""

    def send_invoice(self, invoice: InvoiceContext) -> dict:
        return {
            "status": "success",
            "message": f"Rechnung für {invoice.customer.get('name')} verarbeitet."
        }


def _load_adapter(path: Optional[str]) -> BillingAdapter:
    """Load adapter specified as 'module:Class'."""
    if not path:
        return DummyAdapter()
    module_name, class_name = path.split(":")
    module = import_module(module_name)
    adapter_cls = getattr(module, class_name)
    if not issubclass(adapter_cls, BillingAdapter):
        raise TypeError("Adapter must inherit from BillingAdapter")
    return adapter_cls()


_adapter: Optional[BillingAdapter] = None


def get_adapter() -> BillingAdapter:
    global _adapter
    if _adapter is None:
        _adapter = _load_adapter(settings.billing_adapter)
    return _adapter


def send_to_billing_system(invoice: InvoiceContext) -> dict:
    adapter = get_adapter()
    return adapter.send_invoice(invoice)

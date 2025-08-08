from pydantic import BaseModel
import json


class InvoiceContext(BaseModel):
    type: str
    customer: dict
    service: dict
    amount: dict


def parse_invoice_context(invoice_json: str) -> "InvoiceContext":
    """Parse JSON string into an :class:`InvoiceContext`.

    Raises a ``ValueError`` if the JSON is empty or invalid.
    """
    if not invoice_json or not invoice_json.strip():
        raise ValueError("empty invoice context")
    try:
        data = json.loads(invoice_json)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc
    return InvoiceContext(**data)


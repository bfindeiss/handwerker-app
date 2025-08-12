from pydantic import BaseModel, ValidationError
import json
import re


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

    cleaned = invoice_json.strip()

    # Allow LLM responses wrapped in markdown code fences or additional text.
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc
    try:
        return InvoiceContext(**data)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError("invalid invoice context") from exc


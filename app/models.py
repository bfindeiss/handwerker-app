from pydantic import BaseModel

class InvoiceContext(BaseModel):
    type: str
    customer: dict
    service: dict
    amount: dict
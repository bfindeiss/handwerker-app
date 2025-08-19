from app.conversation import merge_invoice_data
from app.models import InvoiceContext, InvoiceItem


def _invoice_with_items(items):
    return InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde"},
        service={"description": "Fenster einsetzen"},
        items=items,
        amount={},
    )


def test_merge_invoice_preserves_existing_values_and_adds_new_items():
    existing = _invoice_with_items(
        [
            InvoiceItem(
                description="Arbeitszeit Geselle",
                category="labor",
                quantity=1.0,
                unit="h",
                unit_price=50.0,
                worker_role="Geselle",
            ),
            InvoiceItem(
                description="Anfahrt",
                category="travel",
                quantity=15.0,
                unit="km",
                unit_price=0.5,
            ),
        ]
    )

    new = _invoice_with_items(
        [
            InvoiceItem(
                description="Arbeitszeit Geselle",
                category="labor",
                quantity=8.0,
                unit="h",
                unit_price=50.0,
                worker_role="Geselle",
            ),
            InvoiceItem(
                description="Material",
                category="material",
                quantity=1.0,
                unit="Stk",
                unit_price=300.0,
            ),
            InvoiceItem(
                description="Anfahrt",
                category="travel",
                quantity=15.0,
                unit="km",
                unit_price=0.5,
            ),
        ]
    )

    merged = merge_invoice_data(existing, new)

    labor_item = next(i for i in merged.items if i.category == "labor")
    assert labor_item.quantity == 1.0

    assert any(i.category == "material" and i.unit_price == 300.0 for i in merged.items)

    travel_item = next(i for i in merged.items if i.category == "travel")
    assert travel_item.quantity == 15.0

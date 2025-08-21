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


def test_merge_invoice_ignores_placeholder_customer_name():
    existing = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Unbekannter Kunde"},
        service={"description": "Fenster einsetzen"},
        items=[],
        amount={},
    )
    new = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "John Doe"},
        service={},
        items=[],
        amount={},
    )

    merged = merge_invoice_data(existing, new)
    assert merged.customer["name"] == "Unbekannter Kunde"


def test_merge_overwrites_quantity_when_price_placeholder():
    existing = _invoice_with_items(
        [
            InvoiceItem(
                description="Arbeitszeit Geselle",
                category="labor",
                quantity=1.0,
                unit="h",
                unit_price=0.0,
                worker_role="Geselle",
            )
        ]
    )

    new = _invoice_with_items(
        [
            InvoiceItem(
                description="Arbeitszeit Geselle",
                category="labor",
                quantity=5.0,
                unit="h",
                unit_price=55.0,
                worker_role="Geselle",
            )
        ]
    )

    merged = merge_invoice_data(existing, new)

    labor_item = next(i for i in merged.items if i.description == "Arbeitszeit Geselle")
    assert labor_item.quantity == 5.0
    assert labor_item.unit_price == 55.0

def test_merge_removes_labor_placeholder_for_specific_item():
    existing = _invoice_with_items(
        [
            InvoiceItem(
                description="Arbeitszeit Geselle",
                category="labor",
                quantity=1.0,
                unit="h",
                unit_price=0.0,
                worker_role="Geselle",
            )
        ]
    )

    new = _invoice_with_items(
        [
            InvoiceItem(
                description="Fenster einsetzen",
                category="labor",
                quantity=5.0,
                unit="h",
                unit_price=55.0,
                worker_role="Geselle",
            )
        ]
    )

    merged = merge_invoice_data(existing, new)

    assert not any(i.description == "Arbeitszeit Geselle" for i in merged.items)
    labor_items = [i for i in merged.items if i.category == "labor"]
    assert len(labor_items) == 1
    assert labor_items[0].description == "Fenster einsetzen"
    assert labor_items[0].unit_price == 55.0


def test_merge_material_placeholders_with_specific_items():
    existing = _invoice_with_items(
        [
            InvoiceItem(
                description="Materialkosten",
                category="material",
                quantity=1.0,
                unit="Stk",
                unit_price=0.0,
            )
        ]
    )

    new = _invoice_with_items(
        [
            InvoiceItem(
                description="Fenster",
                category="material",
                quantity=1.0,
                unit="Stk",
                unit_price=300.0,
            )
        ]
    )

    merged = merge_invoice_data(existing, new)

    assert not any(i.description == "Materialkosten" for i in merged.items)
    condition = (
        i.description == "Fenster" and i.unit_price == 300.0 for i in merged.items
    )
    assert any(condition)


def test_merge_adds_customer_address_when_missing():
    existing = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde"},
        service={"description": "Fenster einsetzen"},
        items=[],
        amount={},
    )
    new = InvoiceContext(
        type="InvoiceContext",
        customer={"name": "Kunde", "address": "Rathausstr. 11"},
        service={"description": "Fenster einsetzen"},
        items=[],
        amount={},
    )
    merged = merge_invoice_data(existing, new)
    assert merged.customer.get("address") == "Rathausstr. 11"

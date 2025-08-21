from app.service_estimations import estimate_invoice_items, estimate_labor_item
from app.service_templates import SERVICE_TEMPLATES


def test_estimate_labor_item_default_hours():
    item = estimate_labor_item("unbekannte arbeit")
    assert item.quantity == 1.0


def test_estimate_labor_item_fenster_hours():
    item = estimate_labor_item("Fenster einbauen")
    assert item.quantity == 5.0


def test_estimate_invoice_items_tuer_template():
    items = estimate_invoice_items("Bitte eine Tür einsetzen")
    template = SERVICE_TEMPLATES["tuer_setzen"]
    assert [item.description for item in items] == [d["description"] for d in template]

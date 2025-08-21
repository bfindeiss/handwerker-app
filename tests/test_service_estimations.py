from app.service_estimations import estimate_labor_item


def test_estimate_labor_item_default_hours():
    item = estimate_labor_item("unbekannte arbeit")
    assert item.quantity == 0.0


def test_estimate_labor_item_fenster_hours():
    item = estimate_labor_item("Fenster einbauen")
    assert item.quantity == 5.0


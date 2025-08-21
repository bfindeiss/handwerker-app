import pytest

from app.service_estimations import (
    estimate_labor_item,
    estimate_invoice_items,
    generate_invoice_items,
)


def test_estimate_labor_item_default_hours():
    item = estimate_labor_item("unbekannte arbeit")
    assert item.quantity == 1.0


def test_estimate_labor_item_fenster_hours():
    item = estimate_labor_item("Fenster einbauen")
    assert item.quantity == 5.0


def test_generate_invoice_items_parses_free_text():
    items = generate_invoice_items("2 h Reinigung 30 EUR")
    assert len(items) == 1
    item = items[0]
    assert item.description == "Reinigung"
    assert item.quantity == 2
    assert item.unit == "h"
    assert item.unit_price == 30


def test_generate_invoice_items_validation_missing_fields():
    with pytest.raises(ValueError):
        generate_invoice_items("nur text ohne zahlen")


def test_generate_invoice_items_validation_invalid_unit():
    with pytest.raises(ValueError):
        generate_invoice_items("2 tage Arbeit 30 EUR")


def test_estimate_invoice_items_invalid_unit_fallback():
    items = estimate_invoice_items("2 tage Arbeit 30 EUR")
    assert len(items) == 1
    assert items[0].description == "Arbeitszeit Geselle"

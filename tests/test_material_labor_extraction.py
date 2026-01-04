from app.preextract import preextract_candidates


def test_material_labor_and_trip_example():
    text = (
        "Einbau einer Tür und 2 Fenstern, die Tür waren 500€ Materialkosten, "
        "2 Fenster je 200€, dazu 2 Meisterstunden und 4 Gesellenstunden, "
        "35km Anfahrt."
    )
    candidates = preextract_candidates(text)

    window_item = next(
        item
        for item in candidates.materials
        if (item.description or "").casefold() == "fenster"
    )
    assert window_item.quantity == 2.0
    assert window_item.unit_price_cents == 20000

    assert any(
        item.total_price_cents == 50000 for item in candidates.materials if item.total_price_cents
    )

    assert candidates.labor
    assert candidates.labor.meister_hours == 2.0
    assert candidates.labor.geselle_hours == 4.0

    assert candidates.travel
    assert candidates.travel[0].kilometers == 35.0

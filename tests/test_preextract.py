from app.preextract import preextract_candidates, parse_labor_hours


def _find_material(candidates, description: str):
    return next(
        item
        for item in candidates.materials
        if (item.description or "").casefold() == description.casefold()
    )


def test_preextract_material_candidates_variations():
    text = "2 Fenster je 200€"
    candidates = preextract_candidates(text)
    item = _find_material(candidates, "Fenster")
    assert item.quantity == 2.0
    assert item.unit_price_cents == 20000

    text = "Fenster 2x 200 Euro"
    candidates = preextract_candidates(text)
    item = _find_material(candidates, "Fenster")
    assert item.quantity == 2.0
    assert item.unit_price_cents == 20000

    text = "200€ pro Fenster"
    candidates = preextract_candidates(text)
    item = _find_material(candidates, "Fenster")
    assert item.unit_price_cents == 20000
    assert item.quantity is None


def test_preextract_travel_kilometers():
    candidates = preextract_candidates("Anfahrt 12,5 km")
    assert candidates.travel
    assert candidates.travel[0].kilometers == 12.5


def test_parse_labor_hours_roles_and_notes():
    labor = parse_labor_hours("Meisterstunden 2,5 und Gesellenstunden 3 h")
    assert labor.meister_hours == 2.5
    assert labor.geselle_hours == 3.0

    labor = parse_labor_hours("Meister h")
    assert labor.meister_hours is None
    assert any("meister" in note for note in labor.notes)

    labor = parse_labor_hours("2 Stunden Arbeit")
    assert labor.meister_hours is None
    assert labor.geselle_hours is None
    assert any("Rolle" in note for note in labor.notes)


def test_preextract_address_candidate():
    candidates = preextract_candidates("Rathausstr. 11 in 83727 Schliersee")
    assert candidates.address
    address = candidates.address.address
    assert address
    assert address.street == "Rathausstr. 11"
    assert address.postal_code == "83727"
    assert address.city == "Schliersee"

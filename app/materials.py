"""Einfache Preis-Datenbank für Materialien."""

from __future__ import annotations

from typing import Dict

# Feste Beispielpreise für Materialien. In einer echten Anwendung könnten
# diese Daten aus einer Datenbank oder einer externen Quelle stammen.
MATERIAL_PRICES: Dict[str, float] = {
    "schraube": 0.10,
    "dübel": 0.15,
    "klebeband": 2.50,
}


def lookup_material_price(description: str) -> float | None:
    """Sucht den Preis für ein Material anhand seiner Beschreibung.

    Die Suche ist nicht sensitiv gegenüber Groß- und Kleinschreibung. Wird kein
    Preis gefunden, gibt die Funktion ``None`` zurück.
    """

    return MATERIAL_PRICES.get(description.lower())

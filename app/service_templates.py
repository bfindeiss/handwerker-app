"""Vorlagen für typische Dienstleistungen.

Diese Datei definiert einfache Beispielvorlagen, die für automatische
Schätzungen von Rechnungspositionen verwendet werden können. Die
Struktur ist absichtlich simpel gehalten und dient lediglich für Tests
und Demonstrationen.
"""

from __future__ import annotations

from typing import Dict, List

# Jede Vorlage ist eine Liste von Dictionaries, die direkt in
# ``InvoiceItem``-Objekte umgewandelt werden können.

PAINTING_TEMPLATE: List[dict] = [
    {
        "description": "Farbe",
        "category": "material",
        "quantity": 1.0,
        "unit": "stk",
        "unit_price": 0.0,
    },
    {
        "description": "Anfahrt",
        "category": "travel",
        "quantity": 10.0,
        "unit": "km",
        "unit_price": 0.0,
    },
    {
        "description": "Arbeitszeit Geselle",
        "category": "labor",
        "quantity": 4.0,
        "unit": "h",
        "unit_price": 0.0,
        "worker_role": "Geselle",
    },
]

SHOWER_TEMPLATE: List[dict] = [
    {
        "description": "Duschkabine",
        "category": "material",
        "quantity": 1.0,
        "unit": "stk",
        "unit_price": 0.0,
    },
    {
        "description": "Anfahrt",
        "category": "travel",
        "quantity": 15.0,
        "unit": "km",
        "unit_price": 0.0,
    },
    {
        "description": "Arbeitszeit Geselle",
        "category": "labor",
        "quantity": 8.0,
        "unit": "h",
        "unit_price": 0.0,
        "worker_role": "Geselle",
    },
]

# Mapping von Schlüsselwörtern zu den entsprechenden Vorlagen. Enthält
# bewusst mehrere Einträge, damit unterschiedliche Begriffe auf die
# gleiche Vorlage verweisen können.
SERVICE_TEMPLATES: Dict[str, List[dict]] = {
    "malen": PAINTING_TEMPLATE,
    "streichen": PAINTING_TEMPLATE,
    "dusche": SHOWER_TEMPLATE,
    "duschkabine": SHOWER_TEMPLATE,
}

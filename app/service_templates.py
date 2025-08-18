"""Vorlagen für typische Dienstleistungen.

``SERVICE_TEMPLATES`` ordnet sprechenden Schlüsseln eine Liste von Feldern zu,
aus denen ``InvoiceItem``-Instanzen erstellt werden können. Die Vorlagen
werden für automatische Schätzungen von Rechnungspositionen verwendet und
können optional aus JSON- oder YAML-Dateien geladen werden.

Beispielschlüssel:
    - ``malen``/``streichen``: Malerarbeiten.
    - ``dusche``/``duschkabine``: Einbau oder Austausch einer Dusche.
    - ``dusche_einbauen``: Einbau einer neuen Dusche (Arbeitszeit und Material).
    - ``fenster_setzen``: Setzen eines Fensters.

Diese Datei definiert einfache Beispielvorlagen, die für automatische
Schätzungen von Rechnungspositionen verwendet werden können. Die
Struktur ist absichtlich simpel gehalten und dient lediglich für Tests
und Demonstrationen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore


# Beispielvorlagen, die direkt in ``InvoiceItem``-Objekte umgewandelt werden können.
PAINTING_TEMPLATE: List[Dict[str, Any]] = [
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

SHOWER_TEMPLATE: List[Dict[str, Any]] = [
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

# Mapping von Dienstleistungsschlüsseln zu Listen von ``InvoiceItem``-Feldern.
SERVICE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "malen": PAINTING_TEMPLATE,
    "streichen": PAINTING_TEMPLATE,
    "dusche": SHOWER_TEMPLATE,
    "duschkabine": SHOWER_TEMPLATE,
    "dusche_einbauen": [
        {
            "description": "Arbeitszeit Geselle",
            "category": "labor",
            "quantity": 16.0,
            "unit": "h",
            "unit_price": 0.0,
            "worker_role": "Geselle",
        },
        {
            "description": "Duschwanne",
            "category": "material",
            "quantity": 1.0,
            "unit": "Stk",
            "unit_price": 0.0,
        },
    ],
    "fenster_setzen": [
        {
            "description": "Arbeitszeit Geselle",
            "category": "labor",
            "quantity": 8.0,
            "unit": "h",
            "unit_price": 0.0,
            "worker_role": "Geselle",
        },
        {
            "description": "Fensterrahmen",
            "category": "material",
            "quantity": 1.0,
            "unit": "Stk",
            "unit_price": 0.0,
        },
    ],
}


def load_service_templates(path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Lädt Service-Vorlagen aus einer JSON- oder YAML-Datei.

    Args:
        path: Pfad zur Datei mit den Vorlagen.

    Returns:
        Mapping von Dienstleistungs-Schlüsseln zu ``InvoiceItem``-Feldern.
    """

    data = Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        if yaml is None:  # pragma: no cover - optional dependency
            raise RuntimeError("PyYAML ist nicht installiert")
        return yaml.safe_load(data)
    return json.loads(data)

}
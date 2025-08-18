"""Vorlagen für typische Standardarbeiten.

``SERVICE_TEMPLATES`` ordnet sprechenden Schlüsseln eine Liste von Feldern zu,
aus denen ``InvoiceItem``-Instanzen erstellt werden können.

Schlüssel:
    - ``dusche_einbauen``: Einbau einer neuen Dusche.
    - ``fenster_setzen``: Setzen eines Fensters.

Optional können Vorlagen aus JSON- oder YAML-Dateien geladen werden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

# Mapping von Dienstleistungsschlüsseln zu Listen von ``InvoiceItem``-Feldern.
SERVICE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
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

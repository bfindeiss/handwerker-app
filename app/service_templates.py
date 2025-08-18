"""Lädt Standardleistungen für typische Handwerkerarbeiten."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml  # type: ignore[import-untyped]

TEMPLATES_PATH = Path(__file__).with_suffix(".yaml")


def load_templates() -> dict[str, list[dict[str, Any]]]:
    """Lädt die Service-Templates aus der YAML-Datei."""
    with TEMPLATES_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# Geladene Templates als Konstante bereitstellen
SERVICE_TEMPLATES: dict[str, list[dict[str, Any]]] = load_templates()

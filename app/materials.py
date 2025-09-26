"""Verwaltung der Materialpreise."""

from __future__ import annotations

from pathlib import Path
import json
import logging
from threading import RLock
from typing import Dict

from app.settings import settings

logger = logging.getLogger(__name__)

_DEFAULT_PRICES: Dict[str, float] = {
    "schraube": 0.10,
    "dübel": 0.15,
    "klebeband": 2.50,
}

_MATERIAL_PRICES: Dict[str, float] = {}
_LOCK = RLock()


def _load_external_prices() -> Dict[str, float]:
    """Liest optionale Materialpreise aus einer JSON-Datei ein."""

    path = settings.material_prices_path
    if not path:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        return {}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        logger.warning("Invalid material price file %s: %s", file_path, exc)
        return {}
    except OSError as exc:  # pragma: no cover - IO errors
        logger.warning("Unable to read material price file %s: %s", file_path, exc)
        return {}

    cleaned: Dict[str, float] = {}
    for raw_name, raw_price in data.items():
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            logger.debug(
                "Skipping material price for %s because %r is not numeric",
                raw_name,
                raw_price,
            )
            continue
        name = str(raw_name).strip().lower()
        if name:
            cleaned[name] = price
    return cleaned


def _ensure_prices_loaded() -> None:
    with _LOCK:
        if _MATERIAL_PRICES:
            return
        _MATERIAL_PRICES.update(_DEFAULT_PRICES)
        _MATERIAL_PRICES.update(_load_external_prices())


def _persist_prices() -> None:
    path = settings.material_prices_path
    if not path:
        return

    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(_MATERIAL_PRICES, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - IO errors
        logger.warning("Unable to persist material prices to %s: %s", file_path, exc)


def lookup_material_price(description: str) -> float | None:
    """Sucht den Preis für ein Material anhand seiner Beschreibung."""

    if not description:
        return None

    _ensure_prices_loaded()
    with _LOCK:
        return _MATERIAL_PRICES.get(description.lower())


def register_material_price(description: str, unit_price: float, persist: bool = True) -> None:
    """Ergänzt oder aktualisiert einen Materialpreis dynamisch."""

    if not description:
        return

    price = float(unit_price)
    if price <= 0:
        return

    name = description.strip().lower()
    if not name:
        return

    _ensure_prices_loaded()
    with _LOCK:
        current = _MATERIAL_PRICES.get(name)
        if current == price:
            return
        _MATERIAL_PRICES[name] = price
        if persist:
            _persist_prices()


def list_material_prices() -> Dict[str, float]:
    """Gibt eine Kopie der derzeit bekannten Materialpreise zurück."""

    _ensure_prices_loaded()
    with _LOCK:
        return dict(_MATERIAL_PRICES)

"""Deterministische Vorverarbeitung für Extraktionskandidaten."""

from __future__ import annotations

import re

from app.models import (
    Address,
    AddressCandidate,
    MaterialCandidate,
    PreextractCandidates,
    TravelCandidate,
)
from app.parsers.material_labor_parser import (
    Span,
    parse_labor_hours,
    parse_material_candidates,
)


_MONEY_PATTERN = re.compile(
    r"(?P<amount>\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,](?P<dec>\d{1,2}))?\s*(?:€|eur|euro)",
    re.IGNORECASE,
)
_KM_PATTERN = re.compile(
    r"(?P<km>\d+(?:[.,]\d+)?)\s*(?:km|kilometer|kilometern)\b", re.IGNORECASE
)
def _normalize_number(value: str) -> float:
    normalized = value.replace(" ", "").replace(",", ".")
    return float(normalized)


def _parse_money_to_cents(value: str) -> int:
    match = _MONEY_PATTERN.search(value)
    if not match:
        raise ValueError("no money found")
    amount = match.group("amount").replace(" ", "").replace(".", "")
    dec = match.group("dec") or "0"
    dec = dec.ljust(2, "0")[:2]
    return int(amount) * 100 + int(dec)


def _clean_description(desc: str) -> str:
    cleaned = re.sub(r"\s+", " ", desc.strip(" ,.-"))
    return cleaned


def _extract_money_candidates(text: str, used_spans: list[Span]) -> list[MaterialCandidate]:
    candidates: list[MaterialCandidate] = []
    for match in _MONEY_PATTERN.finditer(text):
        span = Span(match.start(), match.end())
        if any(span.overlaps(existing) for existing in used_spans):
            continue
        used_spans.append(span)
        cents = _parse_money_to_cents(match.group(0))
        candidates.append(
            MaterialCandidate(
                total_price_cents=cents,
                source_text=match.group(0),
                notes=["Betrag ohne explizite Menge erkannt"],
            )
        )
    return candidates


def _extract_travel_candidates(text: str) -> list[TravelCandidate]:
    candidates: list[TravelCandidate] = []
    for match in _KM_PATTERN.finditer(text):
        km = _normalize_number(match.group("km"))
        candidates.append(
            TravelCandidate(
                kilometers=km,
                description="Anfahrt",
                source_text=match.group(0),
            )
        )
    return candidates


_ADDRESS_PATTERN = re.compile(
    r"(?P<street>[A-Za-zÄÖÜäöüß.\- ]+\d+)\s*(?:,|in)?\s*"
    r"(?P<postal>\d{5})\s+(?P<city>[A-Za-zÄÖÜäöüß.\- ]+)",
    re.IGNORECASE,
)
_POSTAL_PATTERN = re.compile(r"\b(?P<postal>\d{5})\b")


def _extract_address_candidate(text: str) -> AddressCandidate | None:
    match = _ADDRESS_PATTERN.search(text)
    if not match:
        postal_match = _POSTAL_PATTERN.search(text)
        if not postal_match:
            return None
        return AddressCandidate(
            address=Address(postal_code=postal_match.group("postal")),
            notes=["PLZ erkannt, aber Straße/Ort fehlt"],
        )
    street = _clean_description(match.group("street"))
    postal = match.group("postal")
    city = _clean_description(match.group("city"))
    notes: list[str] = []
    additional_cities = {
        _clean_description(m.group("city"))
        for m in _ADDRESS_PATTERN.finditer(text)
        if _clean_description(m.group("city")) != city
    }
    if additional_cities:
        notes.append("Mehrere Ortsangaben erkannt; mögliche Widersprüche prüfen")
    return AddressCandidate(
        address=Address(street=street, postal_code=postal, city=city),
        notes=notes,
    )


def _validate_address_candidate(
    candidate: AddressCandidate | None, text: str
) -> AddressCandidate | None:
    if candidate is None:
        return None
    address = candidate.address or Address()
    notes = list(candidate.notes)
    if address.postal_code and not address.city:
        after_postal = re.search(
            rf"{address.postal_code}\s+(?P<city>[A-Za-zÄÖÜäöüß.\-]+)", text
        )
        if after_postal:
            address.city = after_postal.group("city")
        else:
            notes.append("PLZ erkannt, aber Ort fehlt")
    if address.city and not address.postal_code:
        match = re.search(r"\b\d{5}\b", text)
        if match:
            address.postal_code = match.group(0)
            notes.append("PLZ aus Kontext ergänzt")
    return AddressCandidate(
        customer_name=candidate.customer_name,
        address=address,
        notes=notes,
    )


def preextract_candidates(text: str) -> PreextractCandidates:
    """Deterministisch extrahiert Material-, Labor-, Reise- und Adresskandidaten."""
    material_candidates, used_spans = parse_material_candidates(text)
    material_candidates.extend(_extract_money_candidates(text, used_spans))
    travel_candidates = _extract_travel_candidates(text)
    labor_candidate = parse_labor_hours(text)
    address_candidate = _validate_address_candidate(_extract_address_candidate(text), text)
    return PreextractCandidates(
        materials=material_candidates,
        travel=travel_candidates,
        labor=labor_candidate,
        address=address_candidate,
    )

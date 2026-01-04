"""Deterministische Vorverarbeitung für Extraktionskandidaten."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.models import (
    Address,
    AddressCandidate,
    LaborCandidate,
    MaterialCandidate,
    PreextractCandidates,
    TravelCandidate,
)


_MONEY_PATTERN = re.compile(
    r"(?P<amount>\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,](?P<dec>\d{1,2}))?\s*(?:€|eur|euro)",
    re.IGNORECASE,
)
_KM_PATTERN = re.compile(
    r"(?P<km>\d+(?:[.,]\d+)?)\s*(?:km|kilometer|kilometern)\b", re.IGNORECASE
)
_MATERIAL_PATTERNS = [
    re.compile(
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?:x|×)?\s+"
        r"(?P<desc>[A-Za-zÄÖÜäöüß.\- ]{2,40})\s+je\s+"
        r"(?P<price>\d+(?:[.,]\d+)?\s*(?:€|eur|euro))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<desc>[A-Za-zÄÖÜäöüß.\- ]{2,40})\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?:x|×)\s*"
        r"(?P<price>\d+(?:[.,]\d+)?\s*(?:€|eur|euro))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<price>\d+(?:[.,]\d+)?\s*(?:€|eur|euro))\s*(?:pro|je)\s+"
        r"(?P<desc>[A-Za-zÄÖÜäöüß.\- ]{2,40})",
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True)
class _Span:
    start: int
    end: int

    def overlaps(self, other: "_Span") -> bool:
        return self.start < other.end and other.start < self.end


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


def _first_match(patterns: Iterable[re.Pattern[str]], text: str) -> Iterable[re.Match[str]]:
    for pattern in patterns:
        for match in pattern.finditer(text):
            yield match


def _clean_description(desc: str) -> str:
    cleaned = re.sub(r"\s+", " ", desc.strip(" ,.-"))
    return cleaned


def _extract_material_candidates(text: str) -> tuple[list[MaterialCandidate], list[_Span]]:
    candidates: list[MaterialCandidate] = []
    used_spans: list[_Span] = []
    for match in _first_match(_MATERIAL_PATTERNS, text):
        span = _Span(match.start(), match.end())
        if any(span.overlaps(existing) for existing in used_spans):
            continue
        used_spans.append(span)
        desc = _clean_description(match.group("desc"))
        qty = match.groupdict().get("qty")
        price = match.group("price")
        quantity = _normalize_number(qty) if qty else None
        unit_price_cents = _parse_money_to_cents(price)
        candidates.append(
            MaterialCandidate(
                description=desc or None,
                quantity=quantity,
                unit="Stk" if quantity is not None else None,
                unit_price_cents=unit_price_cents,
                source_text=match.group(0),
            )
        )
    return candidates, used_spans


def _extract_money_candidates(text: str, used_spans: list[_Span]) -> list[MaterialCandidate]:
    candidates: list[MaterialCandidate] = []
    for match in _MONEY_PATTERN.finditer(text):
        span = _Span(match.start(), match.end())
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


_ROLE_PATTERNS = {
    "meister": [
        re.compile(
            r"(?P<num>\d+(?:[.,]\d+)?)\s*(?:h|std|stunden?)\s*(?:meister)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:meister(?:stunden?| h|std)?)\s*(?P<num>\d+(?:[.,]\d+)?)",
            re.IGNORECASE,
        ),
    ],
    "geselle": [
        re.compile(
            r"(?P<num>\d+(?:[.,]\d+)?)\s*(?:h|std|stunden?)\s*(?:gesell(?:e|en)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:gesell(?:e|en)?(?:stunden?| h|std)?)\s*(?P<num>\d+(?:[.,]\d+)?)",
            re.IGNORECASE,
        ),
    ],
}


def _extract_hours_for_role(text: str, role: str) -> tuple[float | None, list[str]]:
    notes: list[str] = []
    values: list[float] = []
    for pattern in _ROLE_PATTERNS[role]:
        for match in pattern.finditer(text):
            values.append(_normalize_number(match.group("num")))
    if not values:
        if re.search(role, text, re.IGNORECASE):
            notes.append(f"{role} erwähnt, aber keine Stunden erkannt")
        return None, notes
    if len(values) > 1:
        notes.append(f"Mehrere {role}-Stunden erkannt, nehme den ersten Wert")
    return values[0], notes


def parse_labor_hours(text: str) -> LaborCandidate:
    """Extrahiert Meister- und Gesellenstunden aus Text."""
    meister, meister_notes = _extract_hours_for_role(text, "meister")
    geselle, geselle_notes = _extract_hours_for_role(text, "geselle")
    notes = meister_notes + geselle_notes
    if meister is None and geselle is None:
        if re.search(r"stunden|std| h\b", text, re.IGNORECASE):
            notes.append("Stunden erwähnt, aber keine Rolle erkannt")
    return LaborCandidate(meister_hours=meister, geselle_hours=geselle, notes=notes)


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
    material_candidates, used_spans = _extract_material_candidates(text)
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

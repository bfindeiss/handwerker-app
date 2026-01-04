"""Deterministischer Parser für Materialpositionen und Arbeitsstunden."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.models import LaborCandidate, MaterialCandidate


_MONEY_PATTERN = re.compile(
    r"(?P<amount>\d{1,3}(?:[.\s]\d{3})*|\d+)(?:[.,](?P<dec>\d{1,2}))?\s*(?:€|eur|euro)",
    re.IGNORECASE,
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
    re.compile(
        r"(?P<desc>[A-Za-zÄÖÜäöüß.\- ]{2,40})\s+"
        r"(?P<price>\d+(?:[.,]\d+)?\s*(?:€|eur|euro))\s*(?:pro|je)",
        re.IGNORECASE,
    ),
]
_ROLE_REGEX = {
    "meister": r"meister",
    "geselle": r"gesell(?:e|en)?",
}


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    def overlaps(self, other: "Span") -> bool:
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


def parse_material_candidates(text: str) -> tuple[list[MaterialCandidate], list[Span]]:
    candidates: list[MaterialCandidate] = []
    used_spans: list[Span] = []
    for match in _first_match(_MATERIAL_PATTERNS, text):
        span = Span(match.start(), match.end())
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


def _role_patterns(role: str) -> list[re.Pattern[str]]:
    role_token = _ROLE_REGEX[role]
    return [
        re.compile(
            rf"(?P<num>\d+(?:[.,]\d+)?)\s*(?:h|std|stunden?)\s*(?:{role_token})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<num>\d+(?:[.,]\d+)?)\s*(?:{role_token})(?:\s*(?:stunden?|h|std))?",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:{role_token})(?:\s*(?:stunden?|h|std))?\s*(?P<num>\d+(?:[.,]\d+)?)",
            re.IGNORECASE,
        ),
    ]


def _extract_hours_for_role(text: str, role: str) -> tuple[float | None, list[str]]:
    notes: list[str] = []
    values: list[float] = []
    for pattern in _role_patterns(role):
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

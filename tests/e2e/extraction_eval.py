import argparse
import json
import math
from pathlib import Path

import yaml

from app.llm_agent import extract_invoice_context
from app.models import ExtractionResult, format_address, parse_extraction_result


FIELDS = [
    "customer_name",
    "address",
    "material_total_cents",
    "meister_hours",
    "geselle_hours",
    "travel_km",
]


def _load_cases(path: Path) -> list[dict]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _sum_material_cents(extraction: ExtractionResult) -> int | None:
    total = 0
    seen = False
    for item in extraction.line_items:
        if item.type != "material":
            continue
        if item.unit_price_cents is None or item.quantity is None:
            continue
        total += int(item.unit_price_cents * item.quantity)
        seen = True
    return total if seen else None


def _sum_labor_hours(extraction: ExtractionResult, role: str) -> float | None:
    total = 0.0
    seen = False
    for item in extraction.line_items:
        if item.type != "labor" or item.role != role:
            continue
        if item.quantity is None:
            continue
        total += float(item.quantity)
        seen = True
    return total if seen else None


def _sum_travel_km(extraction: ExtractionResult) -> float | None:
    total = 0.0
    seen = False
    for item in extraction.line_items:
        if item.type != "travel" or item.quantity is None:
            continue
        total += float(item.quantity)
        seen = True
    return total if seen else None


def _summarize_extraction(extraction: ExtractionResult) -> dict[str, object]:
    return {
        "customer_name": extraction.customer.name if extraction.customer else None,
        "address": format_address(extraction.customer.address)
        if extraction.customer
        else None,
        "material_total_cents": _sum_material_cents(extraction),
        "meister_hours": _sum_labor_hours(extraction, "meister"),
        "geselle_hours": _sum_labor_hours(extraction, "geselle"),
        "travel_km": _sum_travel_km(extraction),
    }


def _match(expected: object, predicted: object) -> bool:
    if expected is None and predicted is None:
        return True
    if expected is None or predicted is None:
        return False
    if isinstance(expected, float) or isinstance(predicted, float):
        return math.isclose(float(expected), float(predicted), rel_tol=1e-3, abs_tol=1e-2)
    return expected == predicted


def run_eval(cases: list[dict]) -> None:
    stats = {field: {"correct": 0, "predicted": 0, "expected": 0} for field in FIELDS}
    money_diffs: list[int] = []

    for case in cases:
        transcript = case["input"]
        expected = case["expected"]
        raw = extract_invoice_context(transcript)
        extraction = parse_extraction_result(raw)
        predicted = _summarize_extraction(extraction)

        for field in FIELDS:
            exp_val = expected.get(field)
            pred_val = predicted.get(field)
            if exp_val is not None:
                stats[field]["expected"] += 1
            if pred_val is not None:
                stats[field]["predicted"] += 1
            if _match(exp_val, pred_val):
                stats[field]["correct"] += 1

        if expected.get("material_total_cents") is not None:
            diff = abs(
                int(expected["material_total_cents"]) - int(predicted["material_total_cents"] or 0)
            )
            money_diffs.append(diff)

    print("=== Extraktions-Evaluation ===")
    for field, counts in stats.items():
        precision = (
            counts["correct"] / counts["predicted"] if counts["predicted"] else 0.0
        )
        recall = counts["correct"] / counts["expected"] if counts["expected"] else 0.0
        print(
            f"{field}: precision={precision:.2f} "
            f"recall={recall:.2f} (correct={counts['correct']})"
        )

    if money_diffs:
        avg_diff = sum(money_diffs) / len(money_diffs)
        max_diff = max(money_diffs)
        print(f"Material-Summenabweichung: avg={avg_diff:.0f}¢ max={max_diff}¢")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluiert die Extraktionsqualität.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/e2e/eval_cases.yaml"),
        help="Pfad zu den Beispielinputs (YAML oder JSON).",
    )
    args = parser.parse_args()
    cases = _load_cases(args.cases)
    run_eval(cases)


if __name__ == "__main__":
    main()

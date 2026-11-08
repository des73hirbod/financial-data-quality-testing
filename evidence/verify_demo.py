"""Standalone known-answer check for the hand-authored demo fixture.

The reference values below were defined from the intentionally constructed demo
records, not discovered from the application under test.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

EXPECTED = {
    "source_rows": 8,
    "warehouse_rows": 9,
    "source_only_ids": ["103"],
    "warehouse_only_ids": ["109"],
    "shared_distinct_ids": 7,
    "comparable_distinct_ids": 6,
    "ambiguous_shared_ids": ["104"],
    "attribute_mismatches_by_field": {"market_value": 1, "security_name": 1, "currency": 1},
    "attribute_mismatch_count": 3,
}
EXPECTED_CATEGORIES = {
    "ambiguous_match": 1,
    "attribute_mismatch": 3,
    "domain_currency": 1,
    "duplicate_key": 1,
    "extra_record": 1,
    "missing_record": 1,
    "missing_required": 1,
    "negative_market_value": 2,
    "row_count_difference": 1,
}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    metrics = report.get("reconciliation", {})
    diffs = {key: {"expected": val, "actual": metrics.get(key)}
             for key, val in EXPECTED.items() if metrics.get(key) != val}
    found_categories = report.get("summary", {}).get("counts_by_category")
    if found_categories != EXPECTED_CATEGORIES:
        diffs["counts_by_category"] = {"expected": EXPECTED_CATEGORIES, "actual": found_categories}
    status = "PASS" if not diffs else "FAIL"
    print(json.dumps({"status": status, "fixture": "authored demonstration", "differences": diffs}, indent=2))
    return 0 if not diffs else 1

if __name__ == "__main__":
    raise SystemExit(main())

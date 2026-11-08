"""Run CTG source/warehouse checks and write a deterministic, evidence-bearing JSON report."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from csv_loader import CSVLoadError, EXPECTED_COLUMNS, load_csv
from quality_checks import validate_rows
from reconciliation import reconcile

SCHEMA_VERSION = "ctg-quality-report.v1"


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or not isinstance(policy.get("policy_id"), str) or not policy["policy_id"].strip():
        raise ValueError("Policy must be a JSON object with nonempty policy_id")
    required_keys = {"required_fields", "allowed_security_types", "allowed_currencies",
                     "reject_negative_market_value", "allow_zero_market_value",
                     "date_format", "text_comparison", "numeric_tolerance"}
    missing = sorted(required_keys - set(policy))
    if missing:
        raise ValueError(f"Policy missing required settings: {missing}")
    fields = policy["required_fields"]
    if (not isinstance(fields, list) or not all(isinstance(f, str) and f in EXPECTED_COLUMNS for f in fields)):
        raise ValueError("required_fields must be a list of known field names")
    for domain in ("allowed_security_types", "allowed_currencies"):
        allow = policy[domain]
        if allow is not None and (not isinstance(allow, list) or not all(isinstance(v, str) for v in allow)):
            raise ValueError(f"{domain} must be null or a list of strings")
    for flag in ("reject_negative_market_value", "allow_zero_market_value"):
        if not isinstance(policy[flag], bool):
            raise ValueError(f"{flag} must be true/false")
    if policy["date_format"] != "YYYY-MM-DD":
        raise ValueError("This implementation supports only strict YYYY-MM-DD dates")
    if policy.get("numeric_tolerance") not in (None, "0", "0.0", "0.00"):
        raise ValueError("This implementation supports only exact Decimal equality; tolerance policy is not approved")
    if policy.get("text_comparison", "exact-raw") != "exact-raw":
        raise ValueError("Only exact-raw text comparison is implemented")
    return policy


def build_report(source_path: str | Path, warehouse_path: str | Path,
                 policy_path: str | Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    source = load_csv(source_path)
    warehouse = load_csv(warehouse_path)
    validation = validate_rows(source, "source", policy) + validate_rows(warehouse, "warehouse", policy)
    recon = reconcile(source, warehouse, policy)
    issues = validation + recon["issues"]
    issues.sort(key=lambda i: (i["category"], str(i.get("security_id") or ""),
                               str(i.get("field") or ""), i["side"],
                               (i.get("location") or {}).get("line_start", 0)))
    category_counts = dict(sorted(Counter(i["category"] for i in issues).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "run_status": "DATA_VIOLATIONS_FOUND" if issues else "CLEAN",
        "policy_id": policy["policy_id"],
        "policy_authority": "provisional candidate sample-domain allowlists; CTG-specific approved lists, transformations and SLAs unresolved",
        "inputs": {
            "source": {"file": Path(source_path).name, "sha256": sha256(source_path)},
            "warehouse": {"file": Path(warehouse_path).name, "sha256": sha256(warehouse_path)},
        },
        "reconciliation": recon["metrics"],
        "summary": {"finding_count": len(issues), "counts_by_category": category_counts,
                    "validation_findings": len(validation), "reconciliation_findings": len(recon["issues"])},
        "unresolved_policy_questions": [
            "CTG-approved permitted security types and currencies (candidate sample-domain allowlists are not authoritative)",
            "Authorized ETL transformations, currency conversions, formatting and rounding tolerance",
            "Required fields, null encodings, acceptable negative/zero market values",
            "Pipeline blocking SLAs, permitted filtering and record grain over time",
        ],
        "findings": issues,
    }


def write_json_atomic(path: str | Path, report: dict[str, Any]) -> None:
    """Replace report atomically, including error report; never leave a stale all-clear."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dest.parent,
                                     prefix=dest.name + ".", suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        try:
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    os.replace(tmp, dest)


def render_summary(report: dict[str, Any]) -> str:
    lines = ["# CTG Data Quality Run", "", f"**Run status:** {report['run_status']}"]
    if report["run_status"] == "EXECUTION_ERROR":
        lines += ["", "Input or execution failure; no data-cleanliness conclusion.",
                  f"Error: {report['error']['message']}"]
    else:
        r = report["reconciliation"]
        lines += ["", f"Source rows: {r['source_rows']}; warehouse rows: {r['warehouse_rows']}.",
                  f"Source-only IDs: {r['source_only_ids']}; warehouse-only IDs: {r['warehouse_only_ids']}.",
                  f"Shared IDs: {r['shared_distinct_ids']}; safely comparable IDs: {r['comparable_distinct_ids']}; ambiguous IDs: {r['ambiguous_shared_ids']}.",
                  f"Unique-pair attribute mismatches: {r['attribute_mismatch_count']} ({r['attribute_mismatches_by_field']}).",
                  f"Findings: {report['summary']['finding_count']} across categories {report['summary']['counts_by_category']}.",
                  f"Proposed blocking findings: {report.get('proposed_blocker_count', 0)}; mode: {report.get('execution_mode', 'diagnostic')}.",
                  "", "## Interpretation",
                  "The self-test status is separate from this data-check status.",
                  "Source validity problems, destination validity problems and cross-file divergence are reported separately.",
                  "The existence of a mismatch does not establish that the ETL pipeline caused it.",
                  "Currency/type flags use PROVISIONAL sample allowlists, not CTG-approved business rules; they are candidates for confirmation."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--warehouse", required=True)
    p.add_argument("--policy", default=str(Path(__file__).with_name("quality_policy.json")))
    p.add_argument("--report", required=True)
    p.add_argument("--summary")
    p.add_argument("--enforce", action="store_true", help="Return exit 1 for findings marked FAIL_PIPELINE by the provisional policy; default is diagnostic only")
    args = p.parse_args(argv)
    try:
        report = build_report(args.source, args.warehouse, args.policy)
        proposed_blockers = sum(
            finding.get("disposition_proposal") == "FAIL_PIPELINE"
            for finding in report["findings"]
        )
        report["proposed_blocker_count"] = proposed_blockers
        report["execution_mode"] = "provisional_enforcement" if args.enforce else "diagnostic"
        code = 1 if args.enforce and proposed_blockers else 0
    except Exception as exc:  # fail closed for unexpected software errors as well as input errors
        report = {
            "schema_version": SCHEMA_VERSION, "run_status": "EXECUTION_ERROR",
            "inputs": {"source": {"file": Path(args.source).name}, "warehouse": {"file": Path(args.warehouse).name}},
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "findings": None,
        }
        code = 2
    write_json_atomic(args.report, report)
    summary = render_summary(report)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(summary, encoding="utf-8")
    print(summary, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run unit tests in order, then analyze the demo or supplied CSVs and verify known baselines.

Python 3.10+ standard library. Generated outputs go to results/<timestamp>/.
A successful diagnostic run may still find data-quality violations.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
GROUPS = [
    ("01_csv_reader", "test_csv_loader.py", 7),
    ("02_independent_validation", "test_validation.py", 14),
    ("03_reconciliation", "test_reconciliation.py", 16),
    ("04_system_verification", "test_behavior.py", 16),
]
KNOWN_HASHES = {
    "source": "acb7a3b7336a53601185e18996febdb449bd6e5482349d88b0e9052695213fbf",
    "warehouse": "f4c8f4098efc5b06a92c88f3bff0361e388ea598d693ad09e4eee29ec433b890",
}
DEMO_HASHES = {'source': 'd4db78e56f88e26dbf47fede9f6880f6cbd84899f4250f3b9c08f57e1f5da092', 'warehouse': 'e1f890de06deebcd59d5280c84313e98593c386fa89484d2e5a3a2c69852f34c'}



def run_step(title: str, command: list[str], log: Path) -> tuple[int, str]:
    print(f"\n=== {title} ===", flush=True)
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8",
                            errors="replace", stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.write_text("Command: " + json.dumps(command) + "\n\n" + result.stdout,
                   encoding="utf-8")
    print(result.stdout, end="\n" if not result.stdout.endswith("\n") else "", flush=True)
    return result.returncode, result.stdout


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/demo_source.csv")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data/demo_warehouse.csv")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        print("Python 3.10+ required", file=sys.stderr)
        return 2

    destination = ROOT / "results" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination.mkdir(parents=True)
    issues = []
    summary: dict = {"test_groups": [], "real_data_status": "NOT_RUN", "independent_check": "NOT_RUN"}
    print("Results folder:", destination)

    for name, pattern, expected in GROUPS:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"]
        code, output = run_step(name, command, destination / f"{name}.log")
        match = re.search(r"Ran (\d+) tests? in", output)
        count = int(match.group(1)) if match else 0
        passed = code == 0 and count == expected and bool(re.search(r"(?m)^OK\s*$", output))
        summary["test_groups"].append({"group": name, "tests": count, "passed": passed})
        if not passed:
            issues.append(f"{name}: expected {expected} passing tests, observed {count} (exit {code})")

    source, warehouse = args.source.resolve(), args.warehouse.resolve()
    if not source.is_file() or not warehouse.is_file():
        issues.append("Source and/or warehouse CSV not found. See README.md.")
    else:
        cmd = [sys.executable, "run_quality.py", "--source", str(source), "--warehouse", str(warehouse),
               "--policy", "quality_policy.json", "--report", str(destination / "findings.json"),
               "--summary", str(destination / "summary.md")]
        code, _ = run_step("05_real_data_diagnostics", cmd, destination / "05_real_data.log")
        report_path = destination / "findings.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        summary["real_data_status"] = report.get("run_status", "MISSING_REPORT")
        summary["finding_count"] = report.get("summary", {}).get("finding_count")
        if code != 0 or summary["real_data_status"] not in ("CLEAN", "DATA_VIOLATIONS_FOUND"):
            issues.append("Real-data diagnostic failed; see 05_real_data.log")

        if digest(source) == KNOWN_HASHES["source"] and digest(warehouse) == KNOWN_HASHES["warehouse"]:
            cmd = [sys.executable, "evidence/verify_original_ctg.py", "--source", str(source),
                   "--warehouse", str(warehouse)]
            check_code, output = run_step("06_independent_baseline", cmd, destination / "06_independent.log")
            try:
                observed = json.loads(output)["observed"]
                metrics = report.get("reconciliation", {})
                consistent = (metrics.get("source_only_ids") == observed["source_only"]
                              and metrics.get("warehouse_only_ids") == observed["warehouse_only"]
                              and metrics.get("attribute_mismatches_by_field") == observed["mismatches_by_field"]
                              and metrics.get("comparable_distinct_ids") == observed["uniquely_comparable"]
                              and {k: report.get("summary", {}).get("counts_by_category", {}).get(k, 0)
                                   for k in ("domain_currency", "domain_type")}
                                  == observed["candidate_domain_issues"])
            except (ValueError, KeyError, TypeError):
                consistent = False
            summary["independent_check"] = "PASS" if check_code == 0 and consistent else "FAIL"
            if summary["independent_check"] != "PASS":
                issues.append("Independent baseline disagrees with production report")
        elif digest(source) == DEMO_HASHES["source"] and digest(warehouse) == DEMO_HASHES["warehouse"]:
            cmd = [sys.executable, "evidence/verify_demo.py", "--report", str(destination / "findings.json")]
            check_code, _ = run_step("06_demo_known_answer_check", cmd, destination / "06_demo_oracle.log")
            summary["independent_check"] = "PASS" if check_code == 0 else "FAIL"
            if check_code != 0:
                issues.append("Independent demo known-answer check failed")
        else:
            summary["independent_check"] = "SKIPPED: no registered baseline for these inputs"

    summary["total_tests"] = sum(g["tests"] for g in summary["test_groups"])
    summary["overall"] = "PASS" if not issues else "FAIL"
    summary["problems"] = issues
    (destination / "RUN_RESULT.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    result_text = (f"Overall runner: {summary['overall']}\n"
                   f"Automated tests: {summary['total_tests']}/{sum(g[2] for g in GROUPS)} expected\n"
                   f"Real-data status: {summary['real_data_status']}\n"
                   f"Data findings: {summary.get('finding_count')}\n"
                   f"Independent baseline: {summary['independent_check']}\n"
                   f"Evidence: {destination}\n"
                   + ("Problems: " + "; ".join(issues) + "\n" if issues else ""))
    (destination / "RUN_RESULT.txt").write_text(result_text, encoding="utf-8")
    (ROOT / "results" / "LATEST_RESULT.txt").write_text(result_text, encoding="utf-8")
    print("\n" + result_text)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

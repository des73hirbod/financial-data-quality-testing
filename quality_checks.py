"""Per-file CTG data quality checks: preserve evidence, not corrections."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from csv_loader import CSVData, CSVRecord, EXPECTED_COLUMNS


RULES = {
    "missing_key": "R-KEY",
    "duplicate_key": "R-KEY",
    "missing_required": "R-REQ-PROVISIONAL",
    "domain_type": "R-TYPE-DOM",
    "domain_currency": "R-CURRENCY-DOM",
    "invalid_amount": "R-AMOUNT-PARSE",
    "negative_market_value": "R-AMOUNT-NONNEG",
    "invalid_date": "R-DATE-PARSE",
}


def finite_decimal(raw: str) -> Decimal | None:
    """Return a finite decimal or None. Never convert money through float."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def valid_iso_date(raw: str) -> bool:
    """Accept exactly YYYY-MM-DD and actual Gregorian dates."""
    if not isinstance(raw, str) or len(raw) != 10:
        return False
    if raw[4:5] != "-" or raw[7:8] != "-":
        return False
    if not (raw[:4].isascii() and raw[:4].isdigit() and raw[5:7].isascii() and raw[5:7].isdigit() and raw[8:10].isascii() and raw[8:10].isdigit()):
        return False
    try:
        return date.fromisoformat(raw).isoformat() == raw
    except ValueError:
        return False


def location(side: str, record: CSVRecord) -> dict[str, Any]:
    return {"side": side, "line_start": record.line_start, "line_end": record.line_end}


def make_issue(category: str, side: str, record: CSVRecord, field: str,
               policy: dict[str, Any], message: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "category": category,
        "rule_id": ({"ticker": "R-TICKER-REQ", "security_name": "R-NAME-REQ", "security_type": "R-TYPE-REQ", "currency": "R-CURRENCY-REQ", "as_of_date": "R-DATE-REQ", "market_value": "R-AMOUNT-PARSE"}.get(field, RULES[category]) if category == "missing_required" else RULES[category]),
        "side": side,
        "security_id": record.values["security_id"],
        "field": field,
        "location": location(side, record),
        "raw_value": record.values[field],
        "message": message,
        "disposition_proposal": policy.get("proposed_dispositions", {}).get(category, "UNDECIDED"),
        "policy_status": (
            "PROVISIONAL_CANDIDATE_ALLOWLIST" if category in {"domain_type", "domain_currency"}
            else "PROVISIONAL" if category in {"missing_required", "negative_market_value"}
            else "EXPLICIT_OR_REASONABLE_REQUIREMENT"
        ),
    }
    if extra:
        issue.update(extra)
    return issue


def validate_rows(data: CSVData, side: str, policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Check each original row independently; do not mutate or omit any rows."""
    if side not in {"source", "warehouse"}:
        raise ValueError("side must be 'source' or 'warehouse'")
    if data.columns != EXPECTED_COLUMNS:
        raise ValueError("input data has the wrong schema")
    required_fields = set(policy.get("required_fields", ()))
    if not required_fields.issubset(EXPECTED_COLUMNS):
        raise ValueError("policy contains unknown required field")
    for domain in ("allowed_security_types", "allowed_currencies"):
        if policy.get(domain) is not None and (not isinstance(policy[domain], list) or not all(isinstance(v, str) for v in policy[domain])):
            raise ValueError(f"policy {domain} must be null or a list of strings")
    issues: list[dict[str, Any]] = []
    occurrences: dict[str, list[CSVRecord]] = defaultdict(list)
    for record in data.records:
        raw = record.values
        key = raw["security_id"]
        if not key.strip():
            issues.append(make_issue("missing_key", side, record, "security_id", policy, "Security ID is blank"))
        else:
            occurrences[key].append(record)
        for field in EXPECTED_COLUMNS:
            if field != "security_id" and field in required_fields and not raw[field].strip():
                issues.append(make_issue("missing_required", side, record, field, policy, f"Required field {field} is blank or whitespace"))
        for field, conf, category in (
            ("security_type", "allowed_security_types", "domain_type"),
            ("currency", "allowed_currencies", "domain_currency"),
        ):
            allowlist = policy.get(conf)
            if allowlist is not None and raw[field].strip() and raw[field] not in allowlist:
                issues.append(make_issue(category, side, record, field, policy, f"Value not in configured allowlist for {field}", extra={"policy_allowlist": allowlist}))
        amount = finite_decimal(raw["market_value"])
        if amount is None:
            issues.append(make_issue("invalid_amount", side, record, "market_value", policy, "Market value is not a finite decimal"))
        elif amount < 0 and policy.get("reject_negative_market_value", True):
            issues.append(make_issue("negative_market_value", side, record, "market_value", policy, "Negative market value under provisional nonnegative rule"))
        elif amount == 0 and not policy.get("allow_zero_market_value", True):
            issues.append(make_issue("invalid_amount", side, record, "market_value", policy, "Zero market value disallowed under configured policy"))
        if not valid_iso_date(raw["as_of_date"]):
            issues.append(make_issue("invalid_date", side, record, "as_of_date", policy, "Invalid YYYY-MM-DD calendar date"))
    for key, rows in occurrences.items():
        if len(rows) > 1:
            first = rows[0]
            issues.append(make_issue("duplicate_key", side, first, "security_id", policy,
                                     f"Security ID occurs {len(rows)} times", extra={
                "occurrences": len(rows),
                "records": [
                    {"location": location(side, row), "values": dict(row.values)} for row in rows
                ],
            }))
    return sorted(issues, key=lambda d: (d["location"]["line_start"], d["category"], d["field"], d["security_id"]))

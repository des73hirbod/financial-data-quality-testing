"""CTG record identity and attribute reconciliation without lossy joins."""
from __future__ import annotations

from collections import defaultdict, Counter
from typing import Any

from csv_loader import CSVData, CSVRecord
from quality_checks import finite_decimal, valid_iso_date, location

FIELDS = ("ticker", "security_name", "security_type", "currency", "market_value", "as_of_date")


def index_by_key(records: tuple[CSVRecord, ...] | list[CSVRecord]) -> dict[str, list[CSVRecord]]:
    """Map raw nonblank ID to *all* records with that ID; blank IDs remain unmatchable."""
    grouped: dict[str, list[CSVRecord]] = defaultdict(list)
    for record in records:
        key = record.values["security_id"]
        if key.strip():
            grouped[key].append(record)
    return dict(grouped)


def substantive_equal(field: str, left: str, right: str) -> bool:
    """Only money has numeric equivalence; everything else is exact raw text."""
    if field == "market_value":
        a, b = finite_decimal(left), finite_decimal(right)
        if a is not None and b is not None:
            return a == b
    return left == right


def reconcile(source: CSVData, warehouse: CSVData, policy: dict[str, Any]) -> dict[str, Any]:
    """Reconcile identity and attributes under explicit one-to-one matching."""
    src, wh = index_by_key(source.records), index_by_key(warehouse.records)
    source_only = sorted(set(src) - set(wh))
    warehouse_only = sorted(set(wh) - set(src))
    shared = sorted(set(src) & set(wh))
    comparable = [k for k in shared if len(src[k]) == 1 and len(wh[k]) == 1]
    ambiguous = [k for k in shared if len(src[k]) != 1 or len(wh[k]) != 1]
    dispositions = policy.get("proposed_dispositions", {})
    issues: list[dict[str, Any]] = []

    def key_issue(category: str, key: str, rows: list[CSVRecord], side: str, message: str) -> dict[str, Any]:
        return {
            "category": category, "rule_id": "R-RECON", "side": side,
            "security_id": key, "field": "security_id",
            "location": location(side, rows[0]),
            "raw_value": key,
            "records": [{"location": location(side, r), "values": dict(r.values)} for r in rows],
            "message": message,
            "disposition_proposal": dispositions.get(category, "UNDECIDED"),
            "policy_status": "PROVISIONAL_FILTERING_UNKNOWN",
        }
    for key in source_only:
        issues.append(key_issue("missing_record", key, src[key], "source", "Source security ID absent from warehouse"))
    for key in warehouse_only:
        issues.append(key_issue("extra_record", key, wh[key], "warehouse", "Warehouse security ID absent from source"))
    for key in ambiguous:
        s, w = src[key], wh[key]
        issues.append({
            "category": "ambiguous_match", "rule_id": "R-RECON", "side": "paired",
            "security_id": key, "field": "security_id", "raw_value": key,
            "source_occurrences": len(s), "warehouse_occurrences": len(w),
            "source_records": [{"location": location("source", r), "values": dict(r.values)} for r in s],
            "warehouse_records": [{"location": location("warehouse", r), "values": dict(r.values)} for r in w],
            "message": "No authoritative field comparison: key is not unique on both sides",
            "disposition_proposal": dispositions.get("ambiguous_match", "UNDECIDED"),
            "policy_status": "EXPLICIT_KEY_UNIQUENESS_AND_PROVISIONAL_RECONCILIATION",
        })
    for key in comparable:
        a, b = src[key][0], wh[key][0]
        for field in FIELDS:
            av, bv = a.values[field], b.values[field]
            if substantive_equal(field, av, bv):
                continue
            comparison = "exact_decimal" if field == "market_value" and finite_decimal(av) is not None and finite_decimal(bv) is not None else "exact_raw"
            if field == "market_value" and comparison == "exact_raw":
                comparison = "raw_fallback_invalid_numeric"
            issues.append({
                "category": "attribute_mismatch", "rule_id": "R-ATTR-COMP", "side": "paired",
                "security_id": key, "field": field,
                "source_location": location("source", a),
                "warehouse_location": location("warehouse", b),
                "source_raw": av, "warehouse_raw": bv,
                "comparison_policy": comparison,
                "message": "Values differ; pipeline root cause is unproven",
                "disposition_proposal": dispositions.get("attribute_mismatch", "UNDECIDED"),
                "policy_status": "PROVISIONAL_NO_APPROVED_TRANSFORMS",
            })
    counts = Counter(i["field"] for i in issues if i["category"] == "attribute_mismatch")
    metrics = {
        "source_rows": len(source.records), "warehouse_rows": len(warehouse.records),
        "row_count_delta_warehouse_minus_source": len(warehouse.records) - len(source.records),
        "source_distinct_nonblank_ids": len(src), "warehouse_distinct_nonblank_ids": len(wh),
        "source_blank_id_rows": sum(not r.values["security_id"].strip() for r in source.records),
        "warehouse_blank_id_rows": sum(not r.values["security_id"].strip() for r in warehouse.records),
        "source_only_ids": source_only, "warehouse_only_ids": warehouse_only,
        "shared_distinct_ids": len(shared), "comparable_distinct_ids": len(comparable),
        "ambiguous_shared_ids": ambiguous,
        "source_key_multiplicities": {k: len(v) for k, v in sorted(src.items()) if len(v) != 1},
        "warehouse_key_multiplicities": {k: len(v) for k, v in sorted(wh.items()) if len(v) != 1},
        "attribute_mismatches_by_field": dict(sorted(counts.items())),
        "attribute_mismatch_count": sum(counts.values()),
    }
    if metrics["row_count_delta_warehouse_minus_source"] != 0:
        issues.append({
            "category": "row_count_difference", "rule_id": "R-RECON", "side": "paired",
            "security_id": None, "field": None,
            "source_rows": metrics["source_rows"], "warehouse_rows": metrics["warehouse_rows"],
            "difference": metrics["row_count_delta_warehouse_minus_source"],
            "message": "Row counts differ; this does not establish which identities changed",
            "disposition_proposal": dispositions.get("row_count_difference", "UNDECIDED"),
            "policy_status": "PROVISIONAL",
        })
    return {"metrics": metrics, "issues": sorted(issues, key=lambda x: (
        x["category"], x.get("security_id") or "", x.get("field") or "", x.get("source_raw") or ""
    ))}

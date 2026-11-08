# Case study — source-to-warehouse financial data quality

## Engineering question

How can a Python program detect missing records, unexpected records, duplicates, invalid values, and changes between two financial-security snapshots without silently losing evidence or blaming the transfer pipeline for problems already present in its inputs?

## Data model

Each row has seven fields: `security_id`, `ticker`, `security_name`, `security_type`, `currency`, `market_value`, and `as_of_date`. We treat a nonblank raw `security_id` as the provisional record key and compare only uniquely paired IDs. The actual row order is not meaningful.

## Approach

1. Parse the CSV with precise structural errors, preserving original text and line evidence.
2. Check each dataset independently for required values, duplicate IDs, date/amount anomalies and provisional domain constraints.
3. Group by key without overwriting duplicates. Compare key sets, identify ambiguous joins, then compare non-key values only for one-to-one pairs.
4. Verify the application with controlled clean/defective examples and separately declared expected outcomes.
5. Emit structured JSON findings, a readable summary, and distinct exit statuses for clean runs, data violations and execution failures.

## Evidence from the original exercise

In a previously executed local investigation of the original CTG sample (not included in this portfolio repository), the program and a separate raw-CSV verification agreed on the following observed facts:

| Measure | Observed |
|---|---:|
| Source rows | 500 |
| Warehouse rows | 501 |
| Source-only security IDs | 2 |
| Warehouse-only security IDs | 2 |
| Ambiguous duplicated key groups | 1 |
| Safely comparable shared IDs | 497 |
| Attribute mismatches in those unique pairs | 19 |
| Total reported issue entries under provisional domain policy | 33 |

The issue count includes overlaps between categories and three *candidate* domain flags based on provisional allowlists. It is **not** a count of unique bad securities or CTG-confirmed business violations. All 53 automated verification tests passed in the final candidate build; passing tests do not mean the underlying records were valid.

These results require the original version of the source files. To reproduce them, obtain the two CSVs from the [upstream CTG exercise](https://github.com/capitaltg/take-home-assignment-test-engineer-data) and run:

```bash
python run_all_tests.py --source path/to/source_data.csv --warehouse path/to/warehouse_data.csv
```

When the input file hashes match the known exercise version, the runner also executes its independent original-data baseline. Otherwise, it records that the original baseline was skipped, without treating an unfamiliar dataset as an error.

## What a passing test establishes—and what it does not

The 53 automated tests exercise the intended behaviors within their controlled cases. The independent original-data check separately reproduces selected data counts. Neither guarantees absence of unknown defects or establishes financial-business policy. If the warehouse differs from source, the program reports **a difference**, not a proven ETL fault.

## Key design lessons

- Set differences are more informative than row counts alone.
- Preserve key multiplicity: a dict of individual records can erase duplicates.
- Distinguish valid input parsing from financial data validity.
- Compare money numerically with `Decimal`; do not invent tolerances or normalization rules.
- Separate software execution status, automated test outcome, and data-quality findings.

## Limitations

No source-system contract defines accepted currencies/types, authorized transformations, historical record grain, or business failure thresholds. The demo policy is explicitly provisional, and no production deployment, CI infrastructure, or performance benchmark has been claimed.

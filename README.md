# Financial Data Quality & Reconciliation — Python

A small, runnable **data-quality engineering case study**: validate financial-security records, reconcile source and warehouse snapshots, and verify that the detectors themselves behave correctly.

**Python 3.10+ · Standard library only · 53 automated tests · Windows one-click runner**

## Why this project exists

Row counts alone cannot establish that a data transfer preserved the right records. A warehouse can contain missing keys, unexpected keys, duplicates, and altered financial attributes—even when two file lengths appear similar. This project treats *data quality* and *test software correctness* as distinct questions.

Developed as an **AI-assisted learning and engineering project** responding to Capital Technology Group's public [Data Test Engineer exercise](https://github.com/capitaltg/take-home-assignment-test-engineer-data). This is an independent portfolio demonstration, **not an official CTG repository or endorsed solution**. The original task files and CSVs are not redistributed here.

## Run it yourself

1. Download or clone this repository.
2. Use Python 3.10 or newer. No `pip install` needed.
3. On Windows, double-click `RUN_TESTS_WINDOWS.bat`. Alternatively, open a terminal in the project folder and run:

```bash
python run_all_tests.py
```

The runner executes four test groups in order (**7 CSV reader + 14 single-file quality + 16 reconciliation + 16 system behavior = 53 tests**), then analyzes the **included synthetic demo CSVs**, then checks the demo results against a separately declared known-answer oracle. Each run writes logs and JSON findings to a new `results/` folder. Inspect `results/LATEST_RESULT.txt` after the run.

Run only the unit tests:

```bash
python -m unittest discover -s tests -v
```

Run the data checker on your own source and warehouse CSV files (same seven-column schema):

```bash
python run_quality.py --source data/demo_source.csv --warehouse data/demo_warehouse.csv --policy quality_policy.json --report results/demo_findings.json --summary results/demo_summary.md
```

Pass `--source path/to/source.csv --warehouse path/to/warehouse.csv` to `run_all_tests.py` to use your own inputs. The original CTG data, if obtained separately from the source repository, can be used in exactly this way.

## What gets checked

- **Input integrity:** seven-column structure, CSV quoting, malformed rows, precise line reporting, no silent skips.
- **Independent file validation:** required values, duplicate and blank IDs, finite/negative monetary values, real calendar dates, and optional domain allowlists.
- **Reconciliation:** missing and unexpected IDs, count differences, one-to-many ambiguity, six non-key field comparisons. Duplicate key occurrences are preserved rather than overwritten.
- **Test reliability:** known-clean and known-bad cases, ordering invariance, wrong-input paths, deterministic report behavior, proposed enforcement exit codes, and contrast cases.

Monetary values use `Decimal` to compare numeric meaning (`100.0 == 100.00`); other fields retain raw exact comparisons. A mismatch alone does **not** establish an ETL root cause. Domain allowlists and pipeline dispositions are **provisional examples**, not CTG-approved rules.

## Example demonstration outcomes

The included *synthetic* CSVs intentionally contain missing, extra, and duplicate keys, value mismatches, a missing name, a suspicious currency and a negative amount. See [the annotated demonstration data](data/README.md). Passing 53 automated tests means the **testing software** passes its known-answer checks; finding anomalies means the **demo data** is not clean. Those are compatible outcomes.

## Engineering documentation

- [Case study and observed results](docs/CASE_STUDY.md) — includes a separate historical run against the original task data (data not redistributed).
- [Test case matrix](docs/TEST_MATRIX.md) — scenarios and traceability.
- [Decisions, assumptions and limitations](docs/ENGINEERING_DECISIONS.md).
- `evidence/verify_demo.py` checks this repository's authored demo; `evidence/verify_original_ctg.py` only supports the original upstream CSV versions if you download them yourself.

## AI usage and authorship

AI assistance was used extensively in planning, generating and revising implementation code, tests, documentation, and verification scripts. The learning work included studying the actual data, defining test expectations and engineering trade-offs, and interpreting the executed results. This repository is presented as a **documented, reviewed AI-assisted engineering exercise**, not as code written entirely without assistance.

## License and provenance

The public assignment is attributed above. The original task statement, submission template, and source datasets are **not included** because a redistribution license for them was not established. The synthetic demonstration files were authored separately for this project. This repository does not assert any license over CTG materials.

# Test matrix — 24 designed scenarios mapped to executable tests

Source of requirements: CTG `ASSIGNMENT.md`. Case design baseline: completed investigation `TEST_BLUEPRINT.csv`. The actual implementation executes mapped tests; the executable test method is named in the table below; the exact run outcome is in `reports/test_run.log`.

Five coverage groups: G1 input integrity (preserved Stage 11 tests); G2 source/warehouse independent validity; G3 record identity reconciliation; G4 one-to-one attribute reconciliation; G5 evidence and reliability, cross-cutting.

**A successful unittest means the program behaved as expected on controlled inputs; it does not mean the CTG data are clean.**

| ID | Test purpose | Known-answer expected result | Executed test |
|---|---|---|---|
| T-001 | Reject blank key | One blank-ID finding, row retained | `test_T_001_blank_security_id_preserved` |
| T-002 | Detect source-only ID | source_only={2}; source-only rows=1 | `test_T_002_source_only_key` |
| T-003 | Detect warehouse-only ID | warehouse_only={3}; extra rows=1 | `test_T_003_warehouse_only_key` |
| T-004 | Report count delta separately | row_delta=+1 AND duplicate group | `test_T_004_row_count_delta_from_duplicate_not_fake_extra_key` |
| T-005 | Detect swapping at equal counts | delta=0, source_only={2}, warehouse_only={3} | `test_T_005_equal_counts_swapped_ids_detected` |
| T-006 | Preserve duplicate rows | duplicate group 1 multiplicity 2 | `test_T_006_warehouse_duplicate_preserves_both_conflicting_rows` |
| T-007 | Detect source duplicate | source duplicate group key 1, size 2 | `test_T_007_source_duplicate_not_just_warehouse` |
| T-008 | Detect empty or whitespace name | two missing-name candidates, exact line locators | `test_T_008_empty_and_whitespace_names_with_exact_rows` |
| T-009 | Detect missing ticker | one missing-ticker candidate | `test_T_009_missing_ticker_under_explicit_provisional_requiredness` |
| T-010 | Check configured allowed-set | one unsupported-type *under fixture allowlist* | `test_T_010_fixture_security_type_allowlist_and_unknown_real_policy` |
| T-011 | Check configured codes | one unsupported-currency *under fixture allowlist* | `test_T_011_fixture_currency_allowlist_and_unknown_real_policy` |
| T-012 | Flag finite negative amount | one nonnegative-rule candidate; parsed Decimal succeeds | `test_T_012_finite_negative_and_provisional_zero_policy` |
| T-013 | Flag malformed/non-finite money | two parse-failure events; retain raw text | `test_T_013_nonfinite_and_malformed_amounts_are_not_numbers` |
| T-014 | Reject invalid calendar date | one invalid-date finding with raw value | `test_T_014_invalid_calendar_day_and_strict_format` |
| T-015 | Find one changed name | one mismatch security_name with both row locators | `test_T_015_changed_name_preserves_both_raw_values_and_line` |
| T-016 | Catch small amount difference | one market_value mismatch | `test_T_016_decimal_precision_and_numeric_equivalence` |
| T-017 | Avoid false missing/mismatch | zero missing/extra/mismatches | `test_T_017_reordering_does_not_create_differences` |
| T-018 | Do not force duplicate pair | ambiguous key ID1, zero authoritative ID1 field comparisons | `test_T_018_ambiguity_blocks_authoritative_pair_comparison` |
| T-019 | Do not infer ETL caused source issue | SOURCE_ISSUE candidate; zero pair mismatches; no ETL-blame | `test_T_019_source_negative_is_not_an_etl_root_cause` |
| T-020 | Known-clean passes | zero findings under configured fixture rules; PASS | `test_T_020_fully_clean_fixture_is_clean_and_repeatable` |
| T-021 | Keep quoted delimiter inside field | seven fields and ticker raw A,inc | `test_quoted_comma_stays_inside_one_field` |
| T-022 | Reject inconsistent field width | controlled parse error, no silent skip | `test_wrong_width_fails_and_reports_physical_line` |
| T-023 | Expose unapproved case/space changes | two field mismatches under exact raw string default | `test_T_023_case_and_whitespace_are_not_auto_normalized` |
| T-024 | Detect dates that parse but differ | one as_of_date mismatch | `test_T_024_valid_but_different_dates` |

## Test oracle and coverage rules
Each test uses a tiny synthetic controlled fixture with a predetermined expected result, with at least one contrasting clean or failure case where appropriate. Production code contains no CTG-specific defective IDs. Runtime findings are compared independently against the original CSVs after execution.
T-021/022 are deliberately mapped to the existing Stage 11 reader tests, not counted as newly written tests. All twenty-four blueprint IDs have one executed automated test. Additional tests challenge metamorphic reordering, deterministic results, false positives, errors versus clean status, raw key identity, multiplicities, and report provenance.
## Unresolved policy is not an invented guarantee
The CTG brief does not define company-approved currency/type allowlists, exact money tolerance, allowed transformations, or precise field-requiredness. The real-data policy includes **explicitly provisional four-value lists** to demonstrate domain checks (source `XYZ`, warehouse `USX`, warehouse `STOCK_OPTION` flagged as candidates). These are not definitive invalidity judgments. Setting those allowlists to `null` disables their verdicts. The default negative-value and required-field rules are also provisional.

## Execution status

53 automated tests pass on the final package. The 24 mapped cases are a subset of the 53 tests, which also exercise clean controls, parsing failures, policy validation, enforcement decisions, and regression behavior. Reproduce with `python -m unittest discover -s tests -v` or the ordered runner `python run_all_tests.py`.

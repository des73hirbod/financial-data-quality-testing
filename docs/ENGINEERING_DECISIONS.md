# Engineering decisions and limitations

**1. Structural CSV errors fail closed.** Broken row widths or invalid input cause a precise execution error; malformed records are not silently discarded. An empty cell in an otherwise well-formed row remains available for data-quality validation.

**2. Validate the source independently.** An invalid source value can be transferred perfectly and therefore escape a comparison-only checker. Validation and reconciliation answer different questions.

**3. Preserve every duplicate record.** `security_id` maps to a list of occurrences. When either side has multiple records for a key, do not invent a one-to-one match; emit an ambiguity finding and retain both records' evidence.

**4. Preserve meaning of values.** Money uses finite `Decimal` arithmetic with exact numerical equality. Text and dates use exact raw comparison for reconciliation; date validity is checked independently. No unauthorized trimming, case folding, exchange conversion or rounding is introduced.

**5. Make policy explicit, not universal.** Required fields, nonnegative market values, currency/type allowlists and fail/alert dispositions are assumptions for a small illustrative case, not approved financial-domain rules. These controls can be configured in `quality_policy.json`. To avoid provisional domain verdicts, set either allowlist to `null`.

**6. Preserve distinct outcomes.** In diagnostic mode, a successful analysis can return exit code `0` while reporting `DATA_VIOLATIONS_FOUND`. Optional `--enforce` returns `1` for proposed blocking issues; an input/execution error returns `2`. The pipeline-enforcement decisions are examples only.

**7. Verify detectors, not just reports.** The unit tests use known-answer cases including clean controls, bad inputs, duplicates, reordering and incorrect transformations. The independently authored demo oracle checks the fixed authored example; the upstream-data verifier checks only a recognized original file version.

**8. Do not conflate code assistance with demonstrated proficiency.** Generative AI was used extensively to build and refine the code. The useful portfolio evidence is the explicit requirements, runnable tests, traceable decisions, repeatable findings, and explanations of limitations, not an assertion of hand-written implementation.

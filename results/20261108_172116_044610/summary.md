# CTG Data Quality Run

**Run status:** DATA_VIOLATIONS_FOUND

Source rows: 8; warehouse rows: 9.
Source-only IDs: ['103']; warehouse-only IDs: ['109'].
Shared IDs: 7; safely comparable IDs: 6; ambiguous IDs: ['104'].
Unique-pair attribute mismatches: 3 ({'currency': 1, 'market_value': 1, 'security_name': 1}).
Findings: 12 across categories {'ambiguous_match': 1, 'attribute_mismatch': 3, 'domain_currency': 1, 'duplicate_key': 1, 'extra_record': 1, 'missing_record': 1, 'missing_required': 1, 'negative_market_value': 2, 'row_count_difference': 1}.
Proposed blocking findings: 4; mode: diagnostic.

## Interpretation
The self-test status is separate from this data-check status.
Source validity problems, destination validity problems and cross-file divergence are reported separately.
The existence of a mismatch does not establish that the ETL pipeline caused it.
Currency/type flags use PROVISIONAL sample allowlists, not CTG-approved business rules; they are candidates for confirmation.

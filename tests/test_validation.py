"""Explicitly predeclared oracles for CTG T-001,006–014; no real CTG IDs used."""
import unittest
from quality_checks import finite_decimal, valid_iso_date, validate_rows
from common import row, dataset, policy, category


class IndependentValidityTests(unittest.TestCase):
    def evaluate(self, records, *, side='source', **policy_kw):
        return validate_rows(dataset(*records), side, policy(**policy_kw))

    def test_T_001_blank_security_id_preserved(self):
        rows = [row('', line=4), row('21', line=5)]
        data = dataset(*rows)
        findings = validate_rows(data, 'source', policy())
        issue = category(findings, 'missing_key')
        self.assertEqual(len(data.records), 2)
        self.assertEqual(len(issue), 1)
        self.assertEqual(issue[0]['location']['line_start'], 4)
        self.assertEqual(issue[0]['raw_value'], '')
        self.assertEqual(category(self.evaluate([row('21')]), 'missing_key'), [])

    def test_T_006_warehouse_duplicate_preserves_both_conflicting_rows(self):
        records = [row('1', money='100', line=2), row('2', line=3), row('1', money='200', line=4)]
        dups = category(self.evaluate(records, side='warehouse'), 'duplicate_key')
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]['security_id'], '1')
        self.assertEqual(dups[0]['occurrences'], 2)
        self.assertEqual([r['values']['market_value'] for r in dups[0]['records']], ['100', '200'])
        self.assertEqual([r['location']['line_start'] for r in dups[0]['records']], [2, 4])
        self.assertFalse(category(self.evaluate([row('1'), row('2')], side='warehouse'), 'duplicate_key'))

    def test_T_007_source_duplicate_not_just_warehouse(self):
        findings = category(self.evaluate([row('6'), row('6', line=4)]), 'duplicate_key')
        self.assertEqual((len(findings), findings[0]['side'], findings[0]['occurrences']), (1, 'source', 2))
        self.assertEqual(category(self.evaluate([row('6')]), 'duplicate_key'), [])

    def test_T_008_empty_and_whitespace_names_with_exact_rows(self):
        records = [row('1', name='', line=10), row('2', name='   ', line=11), row('3', name='Normal', line=12)]
        issues = category(self.evaluate(records), 'missing_required')
        names = [x for x in issues if x['field'] == 'security_name']
        self.assertEqual([x['location']['line_start'] for x in names], [10, 11])
        self.assertEqual([x['raw_value'] for x in names], ['', '   '])

    def test_T_009_missing_ticker_under_explicit_provisional_requiredness(self):
        bad = row('1');bad.values['ticker'] = ''
        self.assertEqual([i['field'] for i in category(self.evaluate([bad]), 'missing_required')], ['ticker'])
        self.assertEqual(category(self.evaluate([row('1')]), 'missing_required'), [])

    def test_T_010_fixture_security_type_allowlist_and_unknown_real_policy(self):
        records = [row('1', typ='STOCK_OPTION'), row('2', typ='ETF', line=3)]
        strict = category(self.evaluate(records, allowed_security_types=['EQUITY', 'ETF']), 'domain_type')
        self.assertEqual([(x['security_id'], x['raw_value']) for x in strict], [('1', 'STOCK_OPTION')])
        self.assertEqual(category(self.evaluate(records, allowed_security_types=None), 'domain_type'), [])

    def test_T_011_fixture_currency_allowlist_and_unknown_real_policy(self):
        records = [row('1', currency='XYZ'), row('2', currency='USD', line=3)]
        strict = category(self.evaluate(records, allowed_currencies=['USD', 'EUR']), 'domain_currency')
        self.assertEqual([i['raw_value'] for i in strict], ['XYZ'])
        self.assertEqual(category(self.evaluate(records, allowed_currencies=None), 'domain_currency'), [])

    def test_T_012_finite_negative_and_provisional_zero_policy(self):
        invalid = category(self.evaluate([row('1', money='-1.00')]), 'negative_market_value')
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]['raw_value'], '-1.00')
        self.assertEqual(category(self.evaluate([row('1', money='0')]), 'negative_market_value'), [])
        self.assertEqual(category(self.evaluate([row('1', money='5.50')]), 'negative_market_value'), [])

    def test_T_013_nonfinite_and_malformed_amounts_are_not_numbers(self):
        raws = ['NaN', 'Infinity', '-Infinity', 'oops', '']
        records = [row(str(i), money=x, line=i+2) for i,x in enumerate(raws)]
        issues = category(self.evaluate(records), 'invalid_amount')
        self.assertEqual([x['raw_value'] for x in issues], raws)
        self.assertIsNone(finite_decimal('NaN'))
        self.assertIsNone(finite_decimal('oops'))
        self.assertEqual(str(finite_decimal('100.25')), '100.25')

    def test_T_014_invalid_calendar_day_and_strict_format(self):
        records = [row('1', day='2026-02-30'), row('2', day='2026-9-23', line=3)]
        issues = category(self.evaluate(records), 'invalid_date')
        self.assertEqual([x['security_id'] for x in issues], ['1', '2'])
        self.assertTrue(valid_iso_date('2024-02-29'))
        self.assertFalse(valid_iso_date('2025-02-29'))
        self.assertTrue(valid_iso_date('2026-09-23'))

    def test_extra_three_or_more_duplicates_are_all_preserved(self):
        issues = category(self.evaluate([row('1', line=2), row('1', line=3), row('1', line=4)]), 'duplicate_key')
        self.assertEqual(issues[0]['occurrences'], 3)
        self.assertEqual(len(issues[0]['records']), 3)

    def test_lexical_key_identity_not_cast_to_integer(self):
        issues = category(self.evaluate([row('001'), row('1', line=3)]), 'duplicate_key')
        self.assertEqual(issues, [])

    def test_missing_numeric_field_reports_required_and_parse_separately(self):
        issues = self.evaluate([row('5', money='')])
        self.assertEqual(len(category(issues, 'invalid_amount')), 1)
        self.assertEqual(len([i for i in category(issues, 'missing_required') if i['field']=='market_value']), 1)

    def test_positive_control_valid_record_reports_no_issues(self):
        self.assertEqual(self.evaluate([row('1'), row('2', line=3)]), [])


if __name__ == '__main__':
    unittest.main()

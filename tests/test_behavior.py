"""Whole-system and metamorphic controlled oracles, including T-020 clean case."""
import csv
import json
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from csv_loader import EXPECTED_COLUMNS
from run_quality import build_report, load_policy, main
from common import policy


class EndToEndBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source=self.root/'source.csv'; self.wh=self.root/'warehouse.csv'
        self.conf=self.root/'policy.json';self.out=self.root/'findings.json'
        self.conf.write_text(json.dumps(policy(allowed_security_types=['EQUITY','ETF','BOND','MUTUAL_FUND'],allowed_currencies=['USD','EUR','JPY','GBP'])), encoding='utf-8')

    def values(self, key, *, money='100.00', name=None, ticker=None, day='2026-09-23',typ='EQUITY',currency='USD'):
        return [key, ticker if ticker is not None else 'T'+key, name if name is not None else 'Security '+key, typ,currency,money,day]

    def write(self, path, records):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(EXPECTED_COLUMNS);w.writerows(records)

    def setup_clean(self):
        a=[self.values('1'),self.values('2',money='20.00')]
        self.write(self.source,a);self.write(self.wh,a)

    def quiet_main(self, args):
        with contextlib.redirect_stdout(io.StringIO()):
            return main(args)

    def test_T_020_fully_clean_fixture_is_clean_and_repeatable(self):
        self.setup_clean()
        a=build_report(self.source,self.wh,self.conf)
        b=build_report(self.source,self.wh,self.conf)
        self.assertEqual(a['run_status'],'CLEAN')
        self.assertEqual(a['summary']['finding_count'],0)
        self.assertEqual(a,b)
        self.assertEqual(a['reconciliation']['comparable_distinct_ids'],2)

    def test_mutation_changes_exactly_one_attribute(self):
        self.setup_clean(); self.write(self.wh,[self.values('1'),self.values('2',money='20.01')])
        result=build_report(self.source,self.wh,self.conf)
        self.assertEqual(result['summary']['counts_by_category'], {'attribute_mismatch':1})
        f=result['findings'][0]
        self.assertEqual((f['security_id'],f['field'],f['source_raw'],f['warehouse_raw']),('2','market_value','20.00','20.01'))

    def test_metamorphic_row_shuffle_changes_no_substantive_findings(self):
        self.write(self.source,[self.values('1',money='10'), self.values('2',money='20')])
        self.write(self.wh,[self.values('1',money='99'),self.values('3',money='30')])
        a=build_report(self.source,self.wh,self.conf)
        self.write(self.source,[self.values('2',money='20'),self.values('1',money='10')])
        self.write(self.wh,[self.values('3',money='30'),self.values('1',money='99')])
        b=build_report(self.source,self.wh,self.conf)
        self.assertEqual(a['summary'],b['summary'])
        self.assertEqual(a['reconciliation'],b['reconciliation'])
        def facts(r):
            return sorted((i['category'],i.get('security_id'),i.get('field'),i.get('source_raw'),i.get('warehouse_raw')) for i in r['findings'])
        self.assertEqual(facts(a),facts(b))

    def test_deliberate_missing_and_extra_do_not_cancel(self):
        self.write(self.source,[self.values('1'), self.values('2')]);self.write(self.wh,[self.values('1'),self.values('3')])
        result=build_report(self.source,self.wh,self.conf)
        self.assertEqual(result['reconciliation']['row_count_delta_warehouse_minus_source'],0)
        self.assertEqual(result['reconciliation']['source_only_ids'],['2'])
        self.assertEqual(result['reconciliation']['warehouse_only_ids'],['3'])

    def test_injected_duplicate_has_evidence_and_no_ambiguous_field_compare(self):
        self.setup_clean();self.write(self.wh,[self.values('1'),self.values('2',money='20.00'),self.values('1',money='200')])
        result=build_report(self.source,self.wh,self.conf)
        issues=[i for i in result['findings'] if i['category']=='ambiguous_match']
        self.assertEqual(len(issues),1)
        self.assertEqual(issues[0]['security_id'],'1')
        self.assertEqual(len(issues[0]['warehouse_records']),2)
        self.assertEqual([i for i in result['findings'] if i['category']=='attribute_mismatch'],[])

    def test_injected_validity_problems_have_separate_source_warehouse_provenance(self):
        self.write(self.source,[self.values('1',money='-5'),self.values('2')])
        self.write(self.wh,[self.values('1',money='-5'),self.values('2',day='2026-02-30')])
        result=build_report(self.source,self.wh,self.conf)
        source_neg=[i for i in result['findings'] if i['category']=='negative_market_value' and i['side']=='source']
        wh_date=[i for i in result['findings'] if i['category']=='invalid_date' and i['side']=='warehouse']
        self.assertEqual(len(source_neg),1)
        self.assertEqual(len(wh_date),1)
        self.assertEqual(result['summary']['counts_by_category']['attribute_mismatch'],1)

    def test_runner_error_must_overwrite_stale_clean_report(self):
        self.setup_clean()
        code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(self.out.read_text())['run_status'],'CLEAN')
        self.write(self.wh,[self.values('1')[:3]])
        code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,2)
        actual=json.loads(self.out.read_text())
        self.assertEqual(actual['run_status'],'EXECUTION_ERROR')
        self.assertIsNone(actual['findings'])
        self.assertIn('line 2',actual['error']['message'])

    def test_missing_file_is_execution_error_not_clean(self):
        self.setup_clean();self.source.unlink()
        code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(self.out.read_text())['run_status'],'EXECUTION_ERROR')

    def test_invalid_policy_is_not_silently_accepted(self):
        self.setup_clean(); self.conf.write_text(json.dumps(policy(numeric_tolerance='0.1')),encoding='utf-8')
        code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,2)
        self.assertIn('tolerance',json.loads(self.out.read_text())['error']['message'])

    def test_report_contains_input_hashes_and_stable_issue_locations(self):
        self.write(self.source,[self.values('1'), self.values('2')])
        self.write(self.wh,[self.values('1',name='Changed'), self.values('2')])
        report=build_report(self.source,self.wh,self.conf)
        self.assertEqual(len(report['inputs']['source']['sha256']),64)
        issues=[i for i in report['findings'] if i['category']=='attribute_mismatch']
        self.assertEqual((issues[0]['source_location']['line_start'],issues[0]['warehouse_location']['line_start']),(2,2))

    def test_roundtrip_csv_quoted_comma_does_not_create_bad_fields(self):
        a=[self.values('1',ticker='T,one')]
        self.write(self.source,a);self.write(self.wh,a)
        self.assertEqual(build_report(self.source,self.wh,self.conf)['run_status'],'CLEAN')

    def test_incomplete_policy_does_not_downgrade_validation_silently(self):
        self.setup_clean()
        self.conf.write_text('{"policy_id":"incomplete"}',encoding='utf-8')
        code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,2)
        self.assertIn('missing required settings',json.loads(self.out.read_text())['error']['message'])

    def test_enforce_mode_clean_data_returns_success(self):
        self.setup_clean()
        code = self.quiet_main([
            '--source', str(self.source), '--warehouse', str(self.wh),
            '--policy', str(self.conf), '--report', str(self.out), '--enforce'])
        self.assertEqual(code, 0)
        report = json.loads(self.out.read_text())
        self.assertEqual(report['run_status'], 'CLEAN')
        self.assertEqual(report['proposed_blocker_count'], 0)

    def test_enforce_mode_returns_one_for_proposed_blockers(self):
        self.setup_clean()
        self.write(self.wh, [self.values('1'), self.values('3')])
        code = self.quiet_main([
            '--source', str(self.source), '--warehouse', str(self.wh),
            '--policy', str(self.conf), '--report', str(self.out), '--enforce'])
        report = json.loads(self.out.read_text())
        self.assertEqual(code, 1)
        self.assertEqual(report['run_status'], 'DATA_VIOLATIONS_FOUND')
        self.assertGreaterEqual(report['proposed_blocker_count'], 2)
        self.assertEqual(report['execution_mode'], 'provisional_enforcement')

    def test_provisional_domain_alert_does_not_block_enforce_mode(self):
        self.setup_clean()
        bad = [self.values('1', typ='STOCK_OPTION', currency='XYZ'), self.values('2', money='20.00')]
        self.write(self.source, bad)
        self.write(self.wh, bad)
        code = self.quiet_main([
            '--source', str(self.source), '--warehouse', str(self.wh),
            '--policy', str(self.conf), '--report', str(self.out), '--enforce'])
        report = json.loads(self.out.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(report['summary']['counts_by_category'],
                         {'domain_currency': 2, 'domain_type': 2})
        self.assertEqual(report['proposed_blocker_count'], 0)
        self.assertEqual({i['policy_status'] for i in report['findings']},
                         {'PROVISIONAL_CANDIDATE_ALLOWLIST'})

    def test_unexpected_internal_failure_is_not_a_clean_result(self):
        self.setup_clean()
        self.out.write_text('{"run_status":"CLEAN"}',encoding='utf-8')
        with patch('run_quality.build_report',side_effect=RuntimeError('unexpected detector fault')):
            code=self.quiet_main(['--source',str(self.source),'--warehouse',str(self.wh),'--policy',str(self.conf),'--report',str(self.out)])
        self.assertEqual(code,2)
        r=json.loads(self.out.read_text())
        self.assertEqual(r['run_status'],'EXECUTION_ERROR')
        self.assertEqual(r['error']['type'],'RuntimeError')
        self.assertIsNone(r['findings'])


if __name__=='__main__':
    unittest.main()

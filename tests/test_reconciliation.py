"""Known-answer CTG T-002..005,015..019,023,024: key-safe reconciliation."""
import unittest
from reconciliation import index_by_key, reconcile
from quality_checks import validate_rows
from common import row, dataset, policy, category


class ReconciliationTests(unittest.TestCase):
    def r(self, src, wh):
        return reconcile(dataset(*src, side='source'), dataset(*wh, side='warehouse'), policy())

    def test_T_002_source_only_key(self):
        result = self.r([row('1'), row('2')], [row('1')]); metrics = result['metrics']
        self.assertEqual(metrics['source_only_ids'], ['2'])
        issues = category(result['issues'], 'missing_record')
        self.assertEqual([(i['security_id'], i['side']) for i in issues], [('2', 'source')])
        self.assertEqual(self.r([row('1')], [row('1')])['metrics']['source_only_ids'], [])

    def test_T_003_warehouse_only_key(self):
        result = self.r([row('1')], [row('1'), row('3')]); metrics=result['metrics']
        self.assertEqual(metrics['warehouse_only_ids'], ['3'])
        self.assertEqual([x['security_id'] for x in category(result['issues'], 'extra_record')], ['3'])
        self.assertFalse(category(self.r([row('1')],[row('1')])['issues'],'extra_record'))

    def test_T_004_row_count_delta_from_duplicate_not_fake_extra_key(self):
        r=self.r([row('1'),row('2')],[row('1'),row('2'),row('1',line=4)])
        self.assertEqual(r['metrics']['row_count_delta_warehouse_minus_source'],1)
        self.assertEqual(r['metrics']['warehouse_only_ids'],[])
        self.assertEqual(r['metrics']['warehouse_key_multiplicities'],{'1':2})
        self.assertEqual(len(category(r['issues'],'row_count_difference')),1)
        self.assertEqual(r['metrics']['ambiguous_shared_ids'],['1'])

    def test_T_005_equal_counts_swapped_ids_detected(self):
        r=self.r([row('1'),row('2')],[row('1'),row('3')])
        self.assertEqual(r['metrics']['row_count_delta_warehouse_minus_source'],0)
        self.assertEqual(r['metrics']['source_only_ids'], ['2'])
        self.assertEqual(r['metrics']['warehouse_only_ids'], ['3'])

    def test_T_015_changed_name_preserves_both_raw_values_and_line(self):
        r=self.r([row('1',name='Alpha',line=2)],[row('1',name='Beta',line=17)])
        a=category(r['issues'],'attribute_mismatch')
        self.assertEqual([(i['security_id'],i['field']) for i in a],[('1','security_name')])
        self.assertEqual((a[0]['source_raw'],a[0]['warehouse_raw']),('Alpha','Beta'))
        self.assertEqual((a[0]['source_location']['line_start'],a[0]['warehouse_location']['line_start']),(2,17))

    def test_T_016_decimal_precision_and_numeric_equivalence(self):
        equal=self.r([row('1',money='100.0')],[row('1',money='100.00')])
        self.assertFalse(category(equal['issues'],'attribute_mismatch'))
        changed=self.r([row('1',money='100.0000')],[row('1',money='100.0001')])
        mismatches=category(changed['issues'],'attribute_mismatch')
        self.assertEqual([(i['field'],i['comparison_policy']) for i in mismatches],[('market_value','exact_decimal')])

    def test_T_017_reordering_does_not_create_differences(self):
        src=[row('1',line=2),row('2',line=3)]; wh=[row('2',line=2),row('1',line=3)]
        result=self.r(src,wh)
        self.assertEqual(result['metrics']['comparable_distinct_ids'],2)
        self.assertEqual(result['issues'],[])

    def test_T_018_ambiguity_blocks_authoritative_pair_comparison(self):
        r=self.r([row('1',money='50')],[row('1',money='50'),row('1',money='90',line=3)])
        self.assertEqual(r['metrics']['ambiguous_shared_ids'], ['1'])
        self.assertEqual(r['metrics']['comparable_distinct_ids'], 0)
        self.assertEqual(len(category(r['issues'],'ambiguous_match')),1)
        self.assertEqual(category(r['issues'],'attribute_mismatch'),[])
        self.assertEqual(len(category(r['issues'],'ambiguous_match')[0]['warehouse_records']),2)

    def test_T_019_source_negative_is_not_an_etl_root_cause(self):
        a=dataset(row('1',money='-5'),side='source'); b=dataset(row('1',money='-5'),side='warehouse')
        self.assertEqual(len(category(validate_rows(a,'source',policy()),'negative_market_value')),1)
        self.assertEqual(category(reconcile(a,b,policy())['issues'],'attribute_mismatch'),[])

    def test_T_023_case_and_whitespace_are_not_auto_normalized(self):
        a=row('1',ticker='T1',name='ABC'); b=row('1',ticker='T1 ',name='abc')
        diffs=category(self.r([a],[b])['issues'],'attribute_mismatch')
        self.assertEqual([i['field'] for i in diffs],['security_name','ticker'])
        self.assertEqual([i['comparison_policy'] for i in diffs],['exact_raw','exact_raw'])

    def test_T_024_valid_but_different_dates(self):
        diff=category(self.r([row('1',day='2026-09-23')],[row('1',day='2026-09-24')])['issues'],'attribute_mismatch')
        self.assertEqual(len(diff),1)
        self.assertEqual(diff[0]['field'],'as_of_date')

    def test_one_to_many_and_many_to_one_and_many_to_many_all_ambiguous(self):
        for s,w in [([row('1')],[row('1'),row('1',line=3)]),
                    ([row('1'),row('1',line=3)],[row('1')]),
                    ([row('1'),row('1',line=3)],[row('1'),row('1',line=3)])]:
            result=self.r(s,w)
            self.assertEqual(result['metrics']['ambiguous_shared_ids'],['1'])
            self.assertEqual(result['metrics']['comparable_distinct_ids'],0)
            self.assertFalse(category(result['issues'],'attribute_mismatch'))

    def test_unmatchable_blank_ID_never_matches_other_blank_ID(self):
        a=row('');b=row('')
        result=self.r([a],[b])
        self.assertEqual(result['metrics']['shared_distinct_ids'],0)
        self.assertEqual(result['metrics']['source_blank_id_rows'],1)
        self.assertEqual(result['metrics']['warehouse_blank_id_rows'],1)

    def test_original_numeric_formatting_only_is_not_mismatch(self):
        self.assertFalse(category(self.r([row('1',money='1e2')],[row('1',money='100.0')])['issues'],'attribute_mismatch'))

    def test_changed_currency_is_flagged_separately_from_value(self):
        a=row('1',currency='USD',money='100');b=row('1',currency='EUR',money='100')
        issues=category(self.r([a],[b])['issues'],'attribute_mismatch')
        self.assertEqual([i['field'] for i in issues],['currency'])

    def test_raw_key_001_differs_from_key_1(self):
        r=self.r([row('001')],[row('1')])
        self.assertEqual(r['metrics']['source_only_ids'],['001'])
        self.assertEqual(r['metrics']['warehouse_only_ids'],['1'])


if __name__ == '__main__':
    unittest.main()

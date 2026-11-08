"""Independent raw CSV iteration; never imports the testing implementation.

This program independently verifies selected CTG baseline facts. Intended for the
original CTG inputs, not synthetic files. It does not define expected answers
for the production detector; it checks the executed report after the fact.
"""
import argparse
import collections
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--source',required=True)
p.add_argument('--warehouse',required=True)
a=p.parse_args()

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    with open(p,encoding='utf-8-sig',newline='') as file:
        records=list(csv.DictReader(file))
    return records

s=read(a.source); w=read(a.warehouse)
smap=collections.defaultdict(list);wmap=collections.defaultdict(list)
for row in s:smap[row['security_id']].append(row)
for row in w:wmap[row['security_id']].append(row)
shared=set(smap)&set(wmap)
unique=[k for k in shared if len(smap[k])==1 and len(wmap[k])==1]
by_field=collections.Counter()
for k in unique:
    sr,wr=smap[k][0],wmap[k][0]
    for col in ('ticker','security_name','security_type','currency','market_value','as_of_date'):
        if col=='market_value':
            equal=Decimal(sr[col])==Decimal(wr[col])
        else:
            equal=sr[col]==wr[col]
        if not equal:by_field[col]+=1
findings={
'source_hash':digest(a.source),'warehouse_hash':digest(a.warehouse),
'source_rows':len(s),'warehouse_rows':len(w),
'source_only':sorted(set(smap)-set(wmap)),
'warehouse_only':sorted(set(wmap)-set(smap)),
'shared_ids':len(shared),'uniquely_comparable':len(unique),
'warehouse_duplicate_keys':{k:len(v) for k,v in sorted(wmap.items()) if len(v)>1},
'mismatches_by_field':dict(sorted(by_field.items())),
'source_88_name':smap['88'][0]['security_name'],
'source_142_value':smap['142'][0]['market_value'],
'warehouse_301_value':wmap['301'][0]['market_value'],
'warehouse_302_name':wmap['302'][0]['security_name'],
'warehouse_33_values':[r['market_value'] for r in wmap['33']],
'candidate_domain_issues': {
  'domain_currency': sum(r['currency'] not in {'USD','EUR','GBP','JPY'} and bool(r['currency'].strip()) for r in s+w),
  'domain_type': sum(r['security_type'] not in {'EQUITY','ETF','BOND','MUTUAL_FUND'} and bool(r['security_type'].strip()) for r in s+w),
},
}
# Fixed expectations are valid here because the four original input hashes
# identify a known archived assignment version. They are never used by the
# production validator or synthetic fixture generator.
expected={
 'source_hash':'acb7a3b7336a53601185e18996febdb449bd6e5482349d88b0e9052695213fbf',
 'warehouse_hash':'f4c8f4098efc5b06a92c88f3bff0361e388ea598d693ad09e4eee29ec433b890',
 'source_rows':500,'warehouse_rows':501,
 'source_only':['211','377'],'warehouse_only':['901','902'],
 'shared_ids':498,'uniquely_comparable':497,
 'warehouse_duplicate_keys':{'33':2},
 'mismatches_by_field':{'currency':2,'market_value':10,'security_name':6,'security_type':1},
 'source_88_name':'','source_142_value':'-500.0',
 'warehouse_301_value':'-1.0','warehouse_302_name':'',
 'candidate_domain_issues': {'domain_currency':2, 'domain_type':1},
}
errors={k:{'expected':v,'observed':findings.get(k)} for k,v in expected.items() if findings.get(k)!=v}
print(json.dumps({'check':'INDEPENDENT_RAW_CSV_BASELINE','status':'PASS' if not errors else 'FAIL',
 'observed':findings,'expected_mismatches':errors},indent=2,sort_keys=True))
if errors:raise SystemExit(1)

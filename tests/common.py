"""Independent tiny controlled fixtures for test-first CTG verification."""
from csv_loader import CSVData, CSVRecord, EXPECTED_COLUMNS


def row(key='1', *, ticker=None, name=None, typ='EQUITY', currency='USD',
        money='100.00', day='2026-09-23', line=2):
    return CSVRecord(line, line, {
        'security_id': key,
        'ticker': ticker if ticker is not None else ('T'+key),
        'security_name': name if name is not None else ('Security '+key),
        'security_type': typ, 'currency': currency, 'market_value': money,
        'as_of_date': day,
    })


def dataset(*records, side='fixture'):
    return CSVData(side, EXPECTED_COLUMNS, tuple(records))


def policy(**updates):
    import json
    from pathlib import Path
    data = json.loads(Path(__file__).resolve().parents[1].joinpath('quality_policy.json').read_text())
    data.update(updates)
    return data


def category(issues, category_name):
    return [x for x in issues if x['category'] == category_name]

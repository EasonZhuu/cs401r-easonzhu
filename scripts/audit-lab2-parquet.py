"""Audit a downloaded Lab 2 snapshot without running Spark or changing AWS

Usage: python3 scripts/audit-lab2-parquet.py --snapshot PATH --output REPORT.json
Snapshot: raw.csv, processed/, features/, offline/, download-manifest.json
Requires pandas and pyarrow in the selected Python environment
"""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

TRANSACTION_COLUMNS = [
    'transaction_id', 'customer_id', 'purchase_date', 'order_value', 'num_items',
    'payment_method', 'channel', 'store_id', 'product_category',
]
NUMERIC_FEATURES = [
    'days_since_last_purchase', 'customer_tenure_days', 'purchase_frequency_30d',
    'purchase_frequency_90d', 'purchase_frequency_180d', 'avg_order_value',
    'total_spend_90d', 'total_lifetime_value', 'avg_basket_size_6m',
    'category_diversity_score', 'online_to_store_ratio', 'churn_risk_score',
]
ROUNDED_FEATURES = {
    'avg_order_value', 'total_spend_90d', 'total_lifetime_value',
    'avg_basket_size_6m', 'category_diversity_score', 'online_to_store_ratio',
}
FEATURE_COLUMNS = ['customer_id', *NUMERIC_FEATURES, 'loyalty_tier', 'churn_label', 'event_time']
CUTOFF, SNAPSHOT = date(2026, 4, 1), date(2026, 6, 30)


def reference_transactions(path):
    """Independently normalize raw CSV using the published contract

    Exact ranked median uses the lower middle observation for even counts
    Winner selection compares values rather than using Spark window functions
    """
    rows, counts = [], Counter()
    observed = {'order_value': [], 'num_items': []}
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != TRANSACTION_COLUMNS:
            raise ValueError('Unexpected raw CSV schema')
        for raw in reader:
            counts['raw'] += 1
            row = {key: value.strip() or None for key, value in raw.items()}
            if row['customer_id'] is None:
                counts['missing_customer'] += 1
                continue
            for pattern in ('%Y-%m-%d', '%m/%d/%Y'):
                try:
                    row['purchase_date'] = datetime.strptime(row['purchase_date'], pattern).date()
                    break
                except ValueError:
                    pass
            else:
                raise ValueError('Unparseable raw purchase date')
            for key, cast in [('order_value', float), ('num_items', int)]:
                row[key] = None if row[key] is None else cast(row[key])
                if row[key] is not None:
                    if not math.isfinite(row[key]):
                        raise ValueError('Non-finite raw numeric value')
                    observed[key].append(row[key])
            rows.append(row)
    fills = {}
    for key, values in observed.items():
        values.sort()
        fills[key] = values[(len(values)-1)//2]
    winners = {}
    tie_keys = [key for key in TRANSACTION_COLUMNS if key not in ('transaction_id', 'purchase_date', 'order_value')]
    for row in rows:
        for key in fills:
            if row[key] is None:
                row[key] = fills[key]
        for key in ('payment_method', 'channel', 'store_id', 'product_category'):
            if row[key] is None:
                row[key] = 'unknown'
        rank = (row['purchase_date'], row['order_value'], *(row[key] for key in tie_keys))
        previous = winners.get(row['transaction_id'])
        if previous is None or rank > previous[0]:
            winners[row['transaction_id']] = (rank, row)
    counts['after_customer_filter'] = len(rows)
    counts['deduplicated'] = len(winners)
    return [value[1] for value in winners.values()], dict(counts), fills


def reference_features(transactions):
    customers = defaultdict(list)
    holdout_ids = set()
    history_rows = holdout_rows = 0
    for row in transactions:
        if row['purchase_date'] <= CUTOFF:
            customers[row['customer_id']].append(row)
            history_rows += 1
        elif row['purchase_date'] <= SNAPSHOT:
            holdout_ids.add(row['customer_id'])
            holdout_rows += 1
    features = []
    for customer_id, orders in sorted(customers.items()):
        ages = [(CUTOFF-row['purchase_date']).days for row in orders]
        windows = {days: [row for row, age in zip(orders, ages) if 0 <= age < days] for days in (30, 90, 180)}
        ltv = math.fsum(row['order_value'] for row in orders)
        tier = ('Bronze','Silver','Gold','Platinum')[sum(ltv >= bound for bound in (500,2000,5000))]
        recency = min(ages)
        # Independent interpolation of the documented proxy knots
        risk = float(np.interp(recency, [0,30,60,180], [0,0.4,0.7,1]))
        features.append({
            'customer_id': customer_id,
            'days_since_last_purchase': float(recency),
            'customer_tenure_days': float(max(ages)),
            **{f'purchase_frequency_{days}d': float(len(windows[days])) for days in windows},
            'avg_order_value': ltv/len(orders),
            'total_spend_90d': math.fsum(row['order_value'] for row in windows[90]),
            'total_lifetime_value': ltv,
            'avg_basket_size_6m': (math.fsum(row['num_items'] for row in windows[180])/len(windows[180]) if windows[180] else 0.0),
            'category_diversity_score': len({row['product_category'] for row in orders if row['product_category']!='unknown'})/8,
            'online_to_store_ratio': sum(row['channel']=='online' for row in orders)/len(orders),
            'loyalty_tier': tier,
            'churn_risk_score': risk,
            'churn_label': int(customer_id not in holdout_ids),
        })
    return pd.DataFrame(features), {'HistoryRows': history_rows, 'HoldoutRows': holdout_rows, 'HoldoutCustomers': len(holdout_ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checks = []
    report = {
        'VerifiedAtUtc': datetime.now(timezone.utc).isoformat(),
        'Scope': 'All downloaded processed, feature and offline Parquet rows; independent raw-CSV reference',
        'AWSMutationsPerformed': False,
        'AllOnlineRecordsIndependentlyRead': False,
        'Checks': checks,
    }

    def check(name, passed, detail=None):
        checks.append({'Name': name, 'Passed': bool(passed), 'Detail': detail})
        print(f"{'PASS' if passed else 'FAIL'} {name}" + (f': {detail}' if detail is not None else ''))

    def read_group(name, manifest):
        group = manifest['Groups'][name]
        tables, compressions = [], set()
        for obj in group['Files']:
            path = args.snapshot/obj['RelativeLocalPath']
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != obj['LocalSHA256']:
                raise ValueError(f'{name} snapshot hash changed')
            parquet = pq.ParquetFile(path)
            tables.append(parquet.read())
            for i in range(parquet.metadata.num_row_groups):
                rg = parquet.metadata.row_group(i)
                compressions.update(rg.column(j).compression for j in range(rg.num_columns))
        table = pa.concat_tables(tables)
        report.setdefault('Datasets', {})[name] = {
            'S3Prefix': group['Prefix'], 'FileCount': len(tables), 'Rows': table.num_rows,
            'Compression': sorted(compressions),
            'Schema': {field.name: str(field.type) for field in table.schema},
            'InputSHA256': [obj['LocalSHA256'] for obj in group['Files']],
        }
        check(f'{name}: all listed files readable and hashes unchanged', True, f'{len(tables)} files, {table.num_rows} rows')
        return table.to_pandas(), table.schema

    def compare(left, right, key, columns, prefix, tolerances=None):
        if left[key].duplicated().any() or right[key].duplicated().any():
            raise ValueError(f'{prefix}: duplicate comparison key')
        a, b = left.set_index(key).sort_index(), right.set_index(key).sort_index()
        ids_match = a.index.equals(b.index)
        check(f'{prefix}: identifier sets match', ids_match, f'{len(a)} records')
        if not ids_match:
            raise ValueError(f'{prefix}: cannot align different identifier sets')
        for name in columns:
            if pd.api.types.is_numeric_dtype(a[name]):
                tolerance = (tolerances or {}).get(name, 1e-9)
                mask = ~np.isclose(a[name].to_numpy(dtype=float), b[name].to_numpy(dtype=float), atol=tolerance, rtol=0)
                mismatch = int(mask.sum())
                maximum = float(np.max(np.abs(a[name].to_numpy(dtype=float)-b[name].to_numpy(dtype=float))))
                detail = {'Mismatches': mismatch, 'AbsoluteTolerance': tolerance, 'MaxAbsoluteDifference': maximum}
            else:
                mismatch = int((a[name].astype(str)!=b[name].astype(str)).sum())
                detail = {'Mismatches': mismatch}
            check(f'{prefix}: {name}', mismatch==0, detail)

    try:
        manifest = json.loads((args.snapshot/'download-manifest.json').read_text(encoding='utf-8'))
        report.update(Account=manifest['Account'], Bucket=manifest['Bucket'], DownloadedAtUtc=manifest['DownloadedAtUtc'])
        raw_hash = hashlib.sha256((args.snapshot/'raw.csv').read_bytes()).hexdigest()
        check('raw: downloaded CSV hash matches manifest and repository', raw_hash==manifest['RawCSV']['SHA256'] and manifest['RawCSV']['MatchesRepositoryCSV'])
        if raw_hash != manifest['RawCSV']['SHA256']:
            raise ValueError('Raw snapshot hash changed')
        proc, schema = read_group('processed', manifest)
        features, feature_schema = read_group('features', manifest)
        offline, offline_schema = read_group('offline', manifest)
        check('processed: Snappy compression', report['Datasets']['processed']['Compression']==['SNAPPY'])
        check('features: Snappy compression', report['Datasets']['features']['Compression']==['SNAPPY'])
        expected_proc_types = {name: 'string' for name in TRANSACTION_COLUMNS}
        expected_proc_types.update(purchase_date='date32[day]', order_value='double', num_items='int32')
        check('processed: exact nine-column logical schema', {f.name:str(f.type) for f in schema}==expected_proc_types)
        check('processed: no nulls in any column', int(proc.isna().sum().sum())==0, int(proc.isna().sum().sum()))
        check('processed: unique transaction_id', not proc.transaction_id.duplicated().any())
        check('processed: nonempty identifiers', all(proc[name].str.strip().ne('').all() for name in ['transaction_id','customer_id']))
        check('processed: transaction grain preserved', len(proc)>proc.customer_id.nunique(), f'{len(proc)} rows / {proc.customer_id.nunique()} customers')
        check('processed: order_value within contract bounds', proc.order_value.between(0,1000,inclusive='right').all())
        check('processed: num_items within contract bounds', proc.num_items.between(1,100).all())
        check('processed: purchase_date within source version', proc.purchase_date.between(date(2025,4,1),SNAPSHOT).all())
        check('processed: numeric values finite', np.isfinite(proc[['order_value','num_items']].to_numpy()).all())
        check('processed: strings trimmed and nonempty', all(proc[name].str.strip().eq(proc[name]).all() and proc[name].ne('').all() for name in TRANSACTION_COLUMNS if expected_proc_types[name]=='string'))
        expected_rows, source_counts, fills = reference_transactions(args.snapshot/'raw.csv')
        report['RawReference'] = {'Counts': source_counts, 'MedianFillValues': fills}
        check('processed: output count matches independent CSV reference', len(proc)==len(expected_rows), len(proc))
        compare(proc, pd.DataFrame(expected_rows), 'transaction_id', [x for x in TRANSACTION_COLUMNS if x!='transaction_id'], 'processed vs raw reference')
        reference, windows = reference_features(expected_rows)
        report['TemporalWindows'] = {'Cutoff': str(CUTOFF), 'Snapshot': str(SNAPSHOT), **windows}
        types = {name:'double' for name in NUMERIC_FEATURES}
        types.update(customer_id='string', loyalty_tier='string', churn_label='int64', event_time='double')
        check('features: exact 16-column logical schema', {f.name:str(f.type) for f in feature_schema}==types)
        check('features: no nulls', int(features.isna().sum().sum())==0, int(features.isna().sum().sum()))
        check('features: one row per customer', not features.customer_id.duplicated().any())
        check('features: all numeric values finite', np.isfinite(features.select_dtypes(include='number').to_numpy()).all())
        check('features: risk in [0,1]', features.churn_risk_score.between(0,1).all())
        check('features: diversity and online ratio in [0,1]', features[['category_diversity_score','online_to_store_ratio']].ge(0).all().all() and features[['category_diversity_score','online_to_store_ratio']].le(1).all().all())
        check('features: four loyalty tiers', set(features.loyalty_tier)=={'Bronze','Silver','Gold','Platinum'})
        check('features: binary churn labels', set(features.churn_label)=={0,1})
        rate = float(features.churn_label.mean())
        check('features: churn rate 15%-30%', 0.15<=rate<=0.30, rate)
        check('features: non-degenerate risk score', features.churn_risk_score.nunique()>3, int(features.churn_risk_score.nunique()))
        check('features: positive single ingestion event time', features.event_time.nunique()==1 and features.event_time.gt(0).all())
        tolerances = {name:(0.000050001 if name in ROUNDED_FEATURES else 1e-12 if name=='churn_risk_score' else 0) for name in NUMERIC_FEATURES}
        compare(features, reference, 'customer_id', [*NUMERIC_FEATURES,'loyalty_tier','churn_label'], 'features vs historical-CSV reference', tolerances)
        check('offline: Feature Group Created / offline Active', manifest['FeatureGroup']['FeatureGroupStatus']=='Created' and manifest['FeatureGroup']['OfflineStoreStatus']['Status']=='Active')
        check('offline: all feature logical types preserved', all(str(offline_schema.field(name).type)==kind for name,kind in types.items()))
        event_time = float(features.event_time.iloc[0])
        batch = offline.loc[offline.event_time.eq(event_time)].copy()
        check('offline: ingestion batch complete', len(batch)==len(features), f'{len(batch)} batch rows / {len(offline)} total rows')
        check('offline: no deleted batch records', batch.is_deleted.eq(False).all())
        check('offline: no nulls in 16 feature fields', int(batch[FEATURE_COLUMNS].isna().sum().sum())==0)
        check('offline: unique customer within this event_time', not batch.customer_id.duplicated().any())
        compare(batch, features, 'customer_id', [x for x in FEATURE_COLUMNS if x!='customer_id'], 'offline vs job Parquet', {name:0 for name in NUMERIC_FEATURES})
        report['Batch'] = {
            'EventTime': event_time, 'FeatureRows': len(features), 'OfflineRowsForEventTime': len(batch),
            'ChurnLabelCounts': {str(k):int(v) for k,v in features.churn_label.value_counts().items()},
            'ChurnRate': rate, 'LoyaltyTierCounts': {str(k):int(v) for k,v in features.loyalty_tier.value_counts().items()},
            'RecentChurners30Days': int(((features.churn_label==1)&(features.days_since_last_purchase<=30)).sum()),
            'CustomersWithoutRecent180DayOrders': int(features.purchase_frequency_180d.eq(0).sum()),
        }
        report['ParquetContentsIndependentlyRead'] = True
    except Exception as error:
        check('audit completed without exception', False, f'{type(error).__name__}: {error}')
    report['Summary'] = {'Passed': sum(item['Passed'] for item in checks), 'Failed': sum(not item['Passed'] for item in checks)}
    report['AllChecksPassed'] = report['Summary']['Failed']==0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['Summary']))
    return 0 if report['AllChecksPassed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

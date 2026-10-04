# Lab 2 — Full Parquet Audit

Result: **74 checks passed, 0 failed**. This audit reads every record in the
downloaded AWS snapshot, rather than inferring correctness from job status,
object counts or sampled online records.

Machine-readable assertions, physical schemas, file hashes, comparison
tolerances and counts are in [lab2-parquet-audit.json](lab2-parquet-audit.json).
The local audit implementation is [audit-lab2-parquet.py](../scripts/audit-lab2-parquet.py).

## Snapshot and provenance

- Account: `173506956686`; region: `us-east-1`
- Bucket: `northstar-dev-data-173506956686`
- AWS snapshot downloaded on 2026-10-04 UTC / 2026-10-03 America/Denver; exact timestamps are in the JSON report
- The downloaded raw CSV has the same SHA-256 as the repository sample
- S3 file listings and byte sizes were checked at download time; the audit rechecked the recorded SHA-256 of each Parquet file
- Data and the download manifest remain outside Git under the course workspace's `.tools/parquet-validation/` on D:
- The `pyarrow` library and pip cache were added on D:; the existing Python runtime was reused
- AWS operations were reads and downloads; no ETL job, apply, deletion or resource reconfiguration was performed

| Dataset | Parquet files read | Rows read | Grain |
|---------|--------------------|-----------|-------|
| `processed/customers/` | 4 | 157,627 | One row per transaction |
| `features/customers/` | 2 | 9,999 | One row per customer |
| Feature Store's resolved offline data prefix | 54 | 9,999 | One customer record for this ingestion event |

## Processed transaction checks

The physical Parquet schema matches the nine-column data contract: strings,
`purchase_date` as `date32`, `order_value` as `double`, and `num_items` as `int32`.
Both job-output datasets use Snappy compression.

All processed fields are non-null. Identifiers are nonempty, strings are
trimmed, transaction IDs are unique, and repeated customer IDs preserve
transaction history. Dates and numeric values satisfy the v1 contract bounds.
Parquet schema metadata may permit nulls in some fields; the no-null guarantee
here is verified against actual values in this batch.

An independent standard-library implementation read the raw CSV, trimmed and
parsed it, excluded missing customer IDs, imputed missing values using the
exact ranked median, and selected deterministic transaction winners. It does
not import or execute the Spark transform functions.

- Raw rows: 163,255
- Missing-customer rows removed: 3,265
- Duplicate transactions removed: 2,363
- Numeric fill values: `order_value = 141.75`, `num_items = 5`
- All transaction identifiers and all eight remaining fields match the actual processed output, with zero mismatches

## Customer features and temporal labels

The feature dataset has exactly the required 16 fields and expected types,
including an integral `churn_label` and fractional `event_time`. All fields are
non-null, numeric values are finite, and customer IDs are unique.

The independent reference computes features only from the 130,189 historical
transactions on or before 2026-04-01. The 27,438 holdout transactions in
`(2026-04-01, 2026-06-30]` are used only to determine the label.

All 9,999 customers match the reference for all 13 features and the churn
label. Counts and recency/tenure match exactly. The six fields rounded to four
decimal places are compared within their rounding precision; the continuous
risk score is compared within floating-point tolerance. Per-field tolerances
and maximum observed differences are recorded in the JSON report.

- `churn_label = 0`: 7,799 customers
- `churn_label = 1`: 2,200 customers; **22.0022%** of feature customers
- Loyalty tiers: Bronze 3,529; Silver 3,862; Gold 1,664; Platinum 944
- Risk scores stay in `[0,1]` and contain 181 distinct values
- 773 churners had a purchase within 30 days before the cutoff, consistent with a label derived from future holdout activity
- 505 customers had no purchase in the preceding 180-day feature window; their basket-size calculation is finite and matches the guarded reference

## Feature Store offline completeness

The Feature Group was `Created` and its offline store was `Active` in the
download snapshot. All 54 offline Parquet files were read, including the
service-managed fields `write_time`, `api_invocation_time` and `is_deleted`.

For `event_time = 1791073484.0`, the offline store contains exactly 9,999 unique
customer records, with no deleted records and no nulls in the 16 feature fields.
Every field matches the feature job's Parquet output, with zero differences.
This establishes full offline persistence for this batch.

This audit does not independently read every online record. Earlier online
GetRecord samples remain documented in
[feature-engineer verification](lab2-feature-engineer-verification.json).
It also does not establish future SLA compliance or replace the final course
resource-verification script.

## Repeating the local audit

With the retained snapshot and a Python environment containing `pandas` and
`pyarrow`, run from the repository root in Bash:

```bash
SNAPSHOT_DIR=$(cat ../.tools/parquet-validation/latest-snapshot.txt)
python3 scripts/audit-lab2-parquet.py --snapshot "$SNAPSHOT_DIR" \
  --output docs/lab2-parquet-audit.json
```

The snapshot must contain `raw.csv`, `processed/`, `features/`, `offline/` and
`download-manifest.json`. This command reads local files and writes the report;
it performs no AWS operations. Its exit code is nonzero if any check fails.
Older run evidence is preserved as the historical record of what was verified
at that time.

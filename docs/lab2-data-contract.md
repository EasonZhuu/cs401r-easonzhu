## Data Contract: processed/customers

Contract version: **v1**

- Dataset: `s3://northstar-dev-data-173506956686/processed/customers/`
- Format: Snappy-compressed Parquet
- Grain: **one row per transaction**, identified by `transaction_id`
- A customer may have many transactions; `customer_id` is a grouping/join key, not the dataset's unique key
- Scope: the Lab 2 synthetic transaction dataset, covering 2025-04-01 through 2026-06-30

### Producer

Team / process: NorthStar Data Engineering / Glue ETL job `northstar-dev-transform`

Execution role: `northstar-dev-DataEngineer`

The job reads the Glue Catalog table `northstar_dev.customers`, whose source is S3 `raw/customers/`. It trims strings, converts empty strings to nulls, parses the two supported source date formats, casts the schema, removes records without a customer ID, imputes missing values, and deduplicates transactions.

For repeated `transaction_id` values, the job keeps the latest `purchase_date`, then the highest `order_value`; remaining columns break ties deterministically. Output replaces the existing contents of `processed/customers/`. Consumers must wait for a `SUCCEEDED` run and must not read this prefix while the producer is overwriting it.

### Consumers

- Feature engineering job `northstar-dev-feature-engineer`
- (Future) Direct model training in Lab 3, if transaction-level inputs are required

The current feature job aggregates transactions into one row per customer. It computes features only from purchases on or before `2026-04-01`; purchases in `(2026-04-01, 2026-06-30]` are used only for the churn label. Lab 3 normally consumes the resulting customer features, not an unaggregated transaction table.

### Schema

These are the required fields and Spark logical types for an accepted v1 batch. All nine fields must be non-null.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| transaction_id | string | No | Unique transaction identifier; deduplication key |
| customer_id | string | No | Customer identifier; repeated values are expected across different transactions |
| purchase_date | date | No | Purchase date; represented as `YYYY-MM-DD` when displayed or exported as text |
| order_value | double | No | Transaction amount in USD; missing values are filled with the batch median |
| num_items | int | No | Number of items in this transaction; missing values are filled with the rounded batch median |
| payment_method | string | No | Payment method; missing values become `unknown` |
| channel | string | No | Purchase channel: `online` or `store` in this v1 source; `unknown` is the missing-value sentinel |
| store_id | string | No | Store identifier; missing values become `unknown` |
| product_category | string | No | Product category; missing values become `unknown`, which is excluded from category-diversity calculations |

### Quality Guarantees

The following are measurable acceptance requirements for contract v1:

| Requirement | Acceptance assertion |
|-------------|----------------------|
| Complete records | Null count is zero for every schema column; identifiers are non-empty after trimming |
| Transaction uniqueness | `COUNT(DISTINCT transaction_id) = COUNT(*)`; repeated `customer_id` values are allowed |
| Numeric bounds | `0 < order_value <= 1000` USD; `1 <= num_items <= 100` and `num_items` is an integer |
| Valid dates | `purchase_date` is a non-null date in `[2025-04-01, 2026-06-30]` for this Lab 2 dataset version |
| Stable schema | Exactly the nine columns above, with the declared types |
| Missing-category semantics | `unknown` is a sentinel, never an additional real product category |

The numeric bounds are v1 acceptance limits, not sample minima/maxima. The independent reference for the supplied CSV has order values from $15 to $620 and item counts from 1 to 9, within these limits. Different business limits require an agreed contract update.

**Enforcement:** the deployed transform currently fails before writing if `customer_id` is null, `transaction_id` is duplicated, or `purchase_date` is null. Casting, trimming and imputation implement the normalization rules. The remaining acceptance requirements must be checked in the final batch audit; they are not all additional fail-fast assertions in the current producer. A successful job alone is not evidence that every numeric bound was checked. Do not accept a batch that fails the audit.

The assignment's sample phrase "No duplicate customer_id rows" conflicts with the transaction grain specified in Tasks 2 and 3. This contract uses `transaction_id` uniqueness so the consumer retains the purchase history needed for frequency and spend features.

### SLA

- Freshness target: accepted data is available in `processed/customers/` within **2 hours** of the raw batch landing in `raw/customers/`
- Start time: the latest S3 arrival time of an object belonging to the input batch
- Completion time: the successful transform completion time, subject to acceptance checks
- Lab operation: the operator runs the crawler and transform on demand, checks CloudWatch logs and the batch audit, then starts the feature job
- This lab does not yet have an automatic arrival trigger or SLA alarm; the two-hour target is an operating commitment, not an implemented automatic scheduling guarantee
- If a run fails or the deadline is missed, the producer reports the affected batch, error and recovery status to the consumer before it proceeds; the current lab performs this coordination manually

The observed transform execution time of 250 seconds measures job execution, not the complete arrival-to-acceptance freshness interval.

### Versioning

- Schema changes require a new S3 prefix, for example `processed/customers/v2/`
- Breaking changes require consumer notification **5 business days in advance**
- Breaking changes include renamed/removed columns, changed types, changed key/grain, changed null or imputation semantics, and incompatible numeric/date limits
- Consumers explicitly adopt the new prefix; keep the v1 contract and dataset available until the agreed migration is complete
- A data refresh with the same schema and semantics keeps v1; row counts may change and are not fixed acceptance thresholds

Validation evidence for the current lab batch: [transform run](lab2-transform-verification.json), [independent CSV reference](lab2-transform-reference.json), and [downstream feature run](lab2-feature-engineer-verification.json). The subsequent [full Parquet audit](lab2-parquet-audit.md) independently read all 157,627 processed transactions, verified this contract's schema and value bounds, and matched every transaction to the cleaned-CSV reference. It also checked all 9,999 customer feature rows and their offline Feature Store records. The [machine-readable audit](lab2-parquet-audit.json) records 74 passing checks and zero failures. These results accept this recorded batch; future batches still require their own audit, and this does not establish the two-hour freshness SLA.

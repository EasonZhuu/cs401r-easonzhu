"""
Glue ETL: raw/customers/ -> processed/customers/

Reads the crawler-registered catalog table, enforces types, imputes nulls,
removes duplicate transactions, and writes Parquet to the processed zone.

Grain note: this job is transaction-level in and transaction-level out. One
row per purchase, many rows per customer. The feature engineering job is
what collapses to one row per customer. Deduplicating on customer_id here
would destroy the purchase history that RFM features are computed from.

Job arguments (wired by Terraform in modules/glue):
  --database_name  Glue catalog database
  --table_name     catalog table produced by the crawler
  --output_path    s3:// destination for Parquet output
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Target types for the processed zone; crawler-inferred types can differ
# Explicit casts give downstream consumers a consistent schema
SCHEMA = {
    "transaction_id": "string",
    "customer_id": "string",
    "purchase_date": "date",
    "order_value": "double",
    "num_items": "int",
    "payment_method": "string",
    "channel": "string",
    "store_id": "string",
    "product_category": "string",
}

NUMERIC_COLS = ["order_value", "num_items"]
STRING_COLS = ["payment_method", "channel", "store_id", "product_category"]


def cast_types(df):
    """Cast every column to its SCHEMA type. Drop rows with no customer_id.

    Three things to handle, in this order:

    1. TRIM whitespace on every column first. A customer_id of
       "  CUST-10000001 " is not null, but it will not group or join
       correctly either, and the bug is invisible until your feature
       counts come out slightly wrong.
    2. Convert empty strings to real nulls. CSV gives you "" where you
       want None; Spark treats those as different things.
    3. Parse purchase_date. Most rows are ISO 8601 (yyyy-MM-dd) but a few
       percent are MM/dd/yyyy. F.to_date returns null on a format
       mismatch instead of raising, so parse both formats and coalesce.
       If you only parse the ISO form you will silently null out the
       other rows and then drop them.

    Finally, drop rows where customer_id is null. That column is the join
    key for every downstream feature, so a row without it cannot be
    attributed to anyone.
    """
    # Invalid values become null so the next step can impute numeric fields
    df.sparkSession.conf.set("spark.sql.ansi.enabled", "false")
    df.sparkSession.conf.set("spark.sql.legacy.timeParserPolicy", "CORRECTED")

    for name, target_type in SCHEMA.items():
        trimmed = F.trim(F.col(name).cast("string"))
        cleaned = F.when(trimmed == "", F.lit(None)).otherwise(trimmed)

        if target_type == "date":
            typed = F.coalesce(
                F.to_date(cleaned, "yyyy-MM-dd"),
                F.to_date(cleaned, "MM/dd/yyyy"),
            )
        else:
            typed = cleaned.cast(target_type)

        df = df.withColumn(name, typed)

    return df.filter(F.col("customer_id").isNotNull())


def impute_nulls(df):
    """Numeric columns -> column median. String columns -> 'unknown'.

    Use the MEDIAN, not the mean. order_value is right-skewed: a handful
    of large orders drags a mean-imputed value well above the typical
    order and quietly inflates every monetary feature you compute later.

    DataFrame.approxQuantile(col, [0.5], 0.0) gives you an exact median.
    Remember num_items is an integer column - round before you fill it.

    Numeric columns: NUMERIC_COLS.  String columns: STRING_COLS.
    """
    quantiles = df.approxQuantile(NUMERIC_COLS, [0.5], 0.0)
    medians = {}
    for name, values in zip(NUMERIC_COLS, quantiles):
        if not values:
            raise ValueError(f"Cannot compute a median for empty numeric column: {name}")
        median = values[0]
        medians[name] = int(round(median)) if SCHEMA[name] == "int" else float(median)

    return df.fillna(medians).fillna({name: "unknown" for name in STRING_COLS})


def deduplicate(df):
    """Keep one row per transaction_id.

    Deduplicate on transaction_id, NOT on customer_id. A customer is
    expected to have many transactions - that purchase history is exactly
    what the feature engineering job aggregates over in Task 3.
    Collapsing to one row per customer here makes total_lifetime_value
    and purchase_frequency_30d impossible to compute, and you will not
    discover it until Task 3 fails.

    Duplicates are ingestion artifacts: the same transaction landing twice
    from a retry. Break ties deterministically (for example by
    purchase_date descending, then order_value descending) so repeated
    runs produce the same output rather than depending on partition order.

    A window function with row_number() over a partition by transaction_id
    is the idiomatic approach.
    """
    # Remaining columns resolve ties without relying on Spark partition order
    tie_columns = [
        name for name in SCHEMA
        if name not in ("transaction_id", "purchase_date", "order_value")
    ]
    window = Window.partitionBy("transaction_id").orderBy(
        F.col("purchase_date").desc_nulls_last(),
        F.col("order_value").desc_nulls_last(),
        *[F.col(name).desc_nulls_last() for name in tie_columns],
    )
    return (
        df.withColumn("_transaction_rank", F.row_number().over(window))
        .filter(F.col("_transaction_rank") == 1)
        .drop("_transaction_rank")
    )


def main():
    args = getResolvedOptions(
        sys.argv, ["JOB_NAME", "database_name", "table_name", "output_path"]
    )

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    dyf = glue_context.create_dynamic_frame.from_catalog(
        database=args["database_name"],
        table_name=args["table_name"],
    )
    df = dyf.toDF()
    raw_count = df.count()
    print(f"[transform] read {raw_count} raw rows from "
          f"{args['database_name']}.{args['table_name']}")

    df = cast_types(df)
    after_cast = df.count()
    print(f"[transform] after cast_types: {after_cast} rows "
          f"({raw_count - after_cast} dropped for null customer_id)")

    df = impute_nulls(df)
    print(f"[transform] after impute_nulls: {df.count()} rows")

    df = deduplicate(df)
    final_count = df.count()
    print(f"[transform] after deduplicate: {final_count} rows "
          f"({after_cast - final_count} duplicate transactions removed)")

    # Fail loudly rather than writing a bad dataset the feature job will
    # silently consume. These are the same guarantees the data contract
    # published for processed/customers/, enforced at the producer.
    assert df.filter(F.col("customer_id").isNull()).count() == 0, \
        "null customer_id survived the transform"
    assert df.select("transaction_id").distinct().count() == final_count, \
        "duplicate transaction_id survived the transform"
    assert df.filter(F.col("purchase_date").isNull()).count() == 0, \
        "unparseable purchase_date survived the transform"

    (df.coalesce(4)
       .write
       .mode("overwrite")
       .parquet(args["output_path"]))
    print(f"[transform] wrote {final_count} rows to {args['output_path']}")

    job.commit()


if __name__ == "__main__":
    main()

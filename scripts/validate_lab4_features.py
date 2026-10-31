"""Compare shared feature logic with actual Glue Parquet output."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.feature_engineering import FEATURE_COLUMNS, compute_transaction_features


def read_parts(directory):
    parts = sorted(Path(directory).glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(f"No Parquet parts: {directory}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    processed, reference = read_parts(args.processed), read_parts(args.reference)
    computed = compute_transaction_features(processed)
    columns = ["customer_id"] + FEATURE_COLUMNS
    expected = reference[columns].sort_values("customer_id").reset_index(drop=True)
    actual = computed[columns].sort_values("customer_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False,
                                  check_exact=False, atol=0.0001, rtol=0.00001)
    history_ids = set(processed.loc[pd.to_datetime(processed.purchase_date) <= pd.Timestamp("2026-04-01"), "customer_id"])
    assert set(computed.customer_id) == history_ids
    holdout = processed.loc[(pd.to_datetime(processed.purchase_date) > pd.Timestamp("2026-04-01")) &
                            (pd.to_datetime(processed.purchase_date) <= pd.Timestamp("2026-06-30"))]
    labels = (~reference.customer_id.isin(holdout.customer_id)).astype(int)
    assert labels.eq(reference.churn_label).all(), "Reference labels must come from holdout purchases"
    report = {"passed": True, "processed_rows": len(processed), "customers": len(actual),
              "features_compared": FEATURE_COLUMNS, "absolute_tolerance": 0.0001,
              "labels_match_holdout": True,
              "feature_source_sha256": hashlib.sha256(Path("data/feature_engineering.py").read_bytes()).hexdigest(),
              "reference_path": args.reference,
              "note": "Feature equivalence only; historical data does not establish freshness or cloud CI success"}
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

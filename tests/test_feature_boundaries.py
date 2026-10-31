"""Small independent examples cover boundaries absent from the starter tests."""
import pandas as pd
import pytest
from data.feature_engineering import compute_transaction_features, build_churn_feature_set


def transaction(days, **updates):
    row = dict(customer_id="C1", purchase_date=pd.Timestamp("2026-04-01") - pd.Timedelta(days=days),
               order_value=10.0, num_items=2, product_category="Apparel", channel="online")
    row.update(updates)
    return row


def test_exact_window_left_boundary_is_excluded_and_cutoff_is_included():
    rows = pd.DataFrame([transaction(0), transaction(30), transaction(90), transaction(180), transaction(-1)])
    out = compute_transaction_features(rows).iloc[0]
    assert out["purchase_frequency_30d"] == 1
    assert out["purchase_frequency_90d"] == 2
    assert out["purchase_frequency_180d"] == 3
    assert out["total_lifetime_value"] == 40
    assert out["days_since_last_purchase"] == 0


def test_no_transactions_keep_roster_and_fill_documented_defaults():
    rows = pd.DataFrame(columns=["customer_id", "purchase_date", "order_value"])
    roster = pd.DataFrame({"customer_id": ["C1"], "loyalty_tier": ["Bronze"], "churn_label": [1]})
    out = build_churn_feature_set(roster, rows, "2026-04-01").iloc[0]
    assert out["days_since_last_purchase"] == 999
    assert out["purchase_frequency_180d"] == out["avg_basket_size_6m"] == 0
    assert not out.isna().any()


def test_single_order_and_unknown_category():
    out = compute_transaction_features(pd.DataFrame([transaction(5, product_category="unknown")])).iloc[0]
    assert out["days_since_last_purchase"] == out["customer_tenure_days"] == 5
    assert out["avg_order_value"] == 10
    assert out["avg_basket_size_6m"] == 2
    assert out["online_to_store_ratio"] == 1
    assert out["category_diversity_score"] == 0


def test_missing_category_and_channel_do_not_invent_activity():
    out = compute_transaction_features(pd.DataFrame([transaction(5, product_category=None, channel=None)])).iloc[0]
    assert out["category_diversity_score"] == out["online_to_store_ratio"] == 0


def test_duplicate_customer_roster_is_rejected():
    with pytest.raises(ValueError, match="one row"):
        build_churn_feature_set(pd.DataFrame({"customer_id": ["C1", "C1"]}),
                                pd.DataFrame([transaction(5)]), "2026-04-01")

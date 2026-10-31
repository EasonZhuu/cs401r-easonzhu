"""Customer features shared by pandas unit tests and the Glue Spark job.

The cutoff is a business snapshot, not the ingestion timestamp. Only history
at or before that cutoff is allowed to contribute model inputs.
"""
import pandas as pd

FEATURE_CUTOFF = "2026-04-01"
N_CATEGORIES = 8.0
FEATURE_COLUMNS = [
    "days_since_last_purchase", "customer_tenure_days",
    "purchase_frequency_30d", "purchase_frequency_90d", "purchase_frequency_180d",
    "avg_order_value", "total_spend_90d", "total_lifetime_value",
    "avg_basket_size_6m", "category_diversity_score", "online_to_store_ratio",
]


def _history(transactions, snapshot_date):
    frame = transactions.copy()
    frame["purchase_date"] = pd.to_datetime(frame["purchase_date"], errors="raise")
    return frame.loc[frame["purchase_date"] <= pd.Timestamp(snapshot_date)]


def _customers(transactions, customer_ids=None):
    source = transactions if customer_ids is None else customer_ids
    if isinstance(source, pd.DataFrame):
        source = source["customer_id"]
    return pd.DataFrame({"customer_id": pd.Series(source).drop_duplicates().dropna()}).reset_index(drop=True)


def _complete(values, transactions, customer_ids=None, defaults=None):
    out = _customers(transactions, customer_ids).merge(values, on="customer_id", how="left")
    for name, value in (defaults or {}).items():
        out[name] = pd.to_numeric(out[name], errors="raise").fillna(value).astype(float)
    return out


def compute_recency_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    dates = history.groupby("customer_id")["purchase_date"].agg(["min", "max"])
    result = pd.DataFrame({
        "days_since_last_purchase": (pd.Timestamp(snapshot_date) - dates["max"]).dt.days,
        "customer_tenure_days": (pd.Timestamp(snapshot_date) - dates["min"]).dt.days,
    }).reset_index()
    return _complete(result, history, customer_ids,
                     {"days_since_last_purchase": 999, "customer_tenure_days": 0})


def compute_frequency_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    result = _customers(history, customer_ids)
    cutoff = pd.Timestamp(snapshot_date)
    for days in (30, 90, 180):
        name = f"purchase_frequency_{days}d"
        recent = history.loc[history["purchase_date"] > cutoff - pd.Timedelta(days=days)]
        counts = recent.groupby("customer_id").size().rename(name).reset_index()
        result = result.merge(counts, on="customer_id", how="left")
        result[name] = result[name].fillna(0).astype(float)
    return result


def compute_monetary_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    # Zero-order inputs need no num_items column; nonempty data must provide it
    if history.empty and "num_items" not in history:
        history["num_items"] = pd.Series(dtype=float)
    group = history.groupby("customer_id")
    result = group["order_value"].agg(avg_order_value="mean", total_lifetime_value="sum").reset_index()
    cutoff = pd.Timestamp(snapshot_date)
    recent90 = history.loc[history["purchase_date"] > cutoff - pd.Timedelta(days=90)]
    spend = recent90.groupby("customer_id")["order_value"].sum().rename("total_spend_90d").reset_index()
    recent180 = history.loc[history["purchase_date"] > cutoff - pd.Timedelta(days=180)]
    basket = recent180.groupby("customer_id")["num_items"].mean().rename("avg_basket_size_6m").reset_index()
    result = result.merge(spend, on="customer_id", how="left").merge(basket, on="customer_id", how="left")
    return _complete(result, history, customer_ids, dict.fromkeys(
        ["avg_order_value", "total_lifetime_value", "total_spend_90d", "avg_basket_size_6m"], 0))


def compute_behavioral_features(transactions, customer_ids=None):
    history = transactions.copy()
    for name in ("product_category", "channel"):
        if history.empty and name not in history:
            history[name] = pd.Series(dtype=str)
    valid = history.loc[history["product_category"].notna() & history["product_category"].ne("unknown")]
    diversity = (valid.groupby("customer_id")["product_category"].nunique() / N_CATEGORIES).rename("category_diversity_score")
    online = history.assign(_online=history["channel"].eq("online").astype(float)).groupby("customer_id")["_online"].mean().rename("online_to_store_ratio")
    result = diversity.to_frame().join(online, how="outer").reset_index()
    return _complete(result, history, customer_ids,
                     {"category_diversity_score": 0, "online_to_store_ratio": 0})


def compute_transaction_features(transactions, snapshot_date=FEATURE_CUTOFF, customer_ids=None):
    history = _history(transactions, snapshot_date)
    ids = _customers(history, customer_ids)
    result = ids
    parts = [compute_recency_features(history, snapshot_date, ids),
             compute_frequency_features(history, snapshot_date, ids),
             compute_monetary_features(history, snapshot_date, ids),
             compute_behavioral_features(history, ids)]
    for part in parts:
        result = result.merge(part, on="customer_id", how="left", validate="one_to_one")
    return result[["customer_id"] + FEATURE_COLUMNS]


def build_churn_feature_set(customers, transactions, snapshot_date):
    """Attach roster metadata without deriving a label from an input feature."""
    if customers["customer_id"].duplicated().any():
        raise ValueError("Customer roster must have one row per customer")
    features = compute_transaction_features(transactions, snapshot_date, customers[["customer_id"]])
    metadata = customers.drop(columns=[c for c in FEATURE_COLUMNS if c in customers])
    return metadata.merge(features, on="customer_id", validate="one_to_one")

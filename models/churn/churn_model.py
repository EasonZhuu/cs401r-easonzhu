"""Lab4 container-compatible model implementation, migrated from Lab3. No AWS calls."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score


FEATURE_COLUMNS = [
    # Recency and tenure
    "days_since_last_purchase",
    "customer_tenure_days",
    # Frequency
    "purchase_frequency_30d",
    "purchase_frequency_90d",
    "purchase_frequency_180d",
    # Monetary
    "avg_order_value",
    "total_spend_90d",
    "total_lifetime_value",
    "avg_basket_size_6m",
    # Behavioural - these are the features that catch churners who still
    # look active on recency alone. Drop them and your model collapses
    # toward the recency-only baseline.
    "category_diversity_score",
    "online_to_store_ratio",
]

BASELINE_FEATURE = "days_since_last_purchase"

LABEL_COLUMN = "churn_label"

SLICE_COLUMN = "loyalty_tier"

def preprocess_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Clean and prepare features for XGBoost training.
    Returns (X, y) arrays.
    """
    print(f"Preprocessing {len(df):,} samples...")

    required = FEATURE_COLUMNS + [LABEL_COLUMN]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Training data missing required columns: {missing}")
    if not df[LABEL_COLUMN].isin([0, 1]).all():
        raise ValueError("churn_label must contain only 0 or 1, without missing labels")

    # Keep every row aligned with its customer and loyalty tier.
    # Native NaN handling avoids inventing values or fitting an imputer on test data.
    X = df[FEATURE_COLUMNS].to_numpy(dtype=np.float64, copy=True)
    y = df[LABEL_COLUMN].to_numpy(dtype=np.int32, copy=True)
    if np.isinf(X).any():
        raise ValueError("Training features contain infinite values")

    print(f"  Positive class rate: {y.mean():.1%}")
    print(f"  Feature matrix shape: {X.shape}")
    print(f"  Missing feature values: {np.isnan(X).sum()} (native XGBoost handling)")

    return X, y

def train_model(X_train: np.ndarray,
                y_train: np.ndarray,
                X_val: np.ndarray,
                y_val: np.ndarray,
                args) -> xgb.Booster:
    """Train the XGBoost churn model."""

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)

    # Class imbalance, computed from the training split rather than hardcoded.
    # On the reference dataset this lands at 3.545.
    spw = (args.scale_pos_weight if args.scale_pos_weight is not None
           else float((y_train == 0).sum() / max((y_train == 1).sum(), 1)))

    # Record the RESOLVED value so track_run() can log what was actually used.
    # Logging args.scale_pos_weight instead would log None on every run that
    # let it compute itself -- which is most of them -- and your MLflow
    # comparison would be missing the one parameter most likely to explain a
    # precision/recall difference between runs.
    args.resolved_scale_pos_weight = spw

    params = {
        # eval_metric ORDER MATTERS. XGBoost early-stops on the LAST metric in
        # this list, not the first. This used to read ["auc", "logloss"], which
        # silently made logloss the early-stopping criterion: under
        # scale_pos_weight the reweighted logloss keeps improving long after
        # ranking quality peaks, so training ran the full 200 rounds instead of
        # stopping near round 31 and validation AUC came out 0.7603 instead of
        # 0.7822. Measured across 50 splits, that cost the model the promotion
        # gate on 28% of them -- a student doing everything right was told their
        # features did not beat recency. Keep "auc" last (defect 49).
        "objective": "binary:logistic",
        "tree_method": "hist",
        "nthread": 2,
        # Lab4 requires increasing dormancy to preserve the direction of risk
        "monotone_constraints": "(" + ",".join("1" if name == BASELINE_FEATURE else "0"
                                                   for name in FEATURE_COLUMNS) + ")",
        "eval_metric": ["logloss", "auc"],
        "max_depth": args.max_depth,
        "eta": args.eta,
        "min_child_weight": args.min_child_weight,
        "subsample": args.subsample,
        "colsample_bytree": args.colsample_bytree,
        "scale_pos_weight": spw,
        "seed": args.seed,
        "verbosity": 1,
    }

    print(f"\nTraining XGBoost with params: {json.dumps(params, indent=2)}")

    history = {}
    model = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=args.num_round,
        evals=[(dtrain, "train"), (dval, "validation")],
        evals_result=history,
        callbacks=[xgb.callback.EarlyStopping(
            rounds=20, data_name="validation", metric_name="auc",
            maximize=True, save_best=True,
        )],
        verbose_eval=25,
    )

    # XGBoost 1.7 can discard best_score when save_best slices the booster
    best_score = float(model.attr("best_score") or max(history["validation"]["auc"]))
    print(f"Best validation AUC: {best_score:.6f}; "
          f"retained boosting rounds: {model.num_boosted_rounds()}")
    return model

EVAL_THRESHOLDS = {
    "precision_top10":   0.50,   # Minimum precision @ top 10% scored customers
    "recall_top10":      0.25,   # Minimum recall @ top 10% scored customers
    # Note the recall ceiling: with ~22% positives, targeting the top 10% of
    # customers caps achievable recall near 0.45. Hitting 0.25 means capturing
    # roughly half of what is reachable within that contact budget.
}

BOOTSTRAP_N = 2000

BOOTSTRAP_SEED = 42

def train_recency_baseline(X_train: np.ndarray,
                           y_train: np.ndarray,
                           X_val: np.ndarray, seed: int = 42) -> np.ndarray:
    """Train the recency-only baseline and score the validation split.

    The baseline is a model over `days_since_last_purchase` ALONE, trained on
    the same training rows and scored on the same validation rows as the full
    model. That is what makes the comparison fair.

    It is deliberately NOT a constant predictor. A constant prediction has an
    AUC of exactly 0.5 by construction, so "beating" it proves only that your
    model is better than a coin flip. The question Lab 3 asks is whether your
    feature engineering beats the rule the business already has for free:
    "contact whoever has not purchased in a while."
    """
    i = FEATURE_COLUMNS.index(BASELINE_FEATURE)
    dtr = xgb.DMatrix(X_train[:, [i]], label=y_train, feature_names=[BASELINE_FEATURE])
    dva = xgb.DMatrix(X_val[:, [i]], feature_names=[BASELINE_FEATURE])
    spw = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    params = {
        "objective": "binary:logistic", "eval_metric": "auc", "tree_method": "hist", "nthread": 2,
        "max_depth": 4, "eta": 0.1, "subsample": 0.9,
        "colsample_bytree": 0.9, "scale_pos_weight": spw, "seed": seed,
    }
    return xgb.train(params, dtr, num_boost_round=200).predict(dva)

def bootstrap_lift_ci(y_true: np.ndarray,
                      proba: np.ndarray,
                      baseline_proba: np.ndarray,
                      n: int = BOOTSTRAP_N,
                      seed: int = BOOTSTRAP_SEED,
                      alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI for (model AUC - baseline AUC), by resampling the val set.

    PAIRED: each replicate resamples row indices once and scores BOTH models on
    those same rows, so the interval is on the difference and the correlation
    between the two models is preserved. Resampling them independently breaks
    the pairing and inflates the interval, which would make a real improvement
    look inconclusive.

    Replicates whose resample happens to be single-class are skipped, because
    AUC is undefined there.

    The seed is fixed so the gate is reproducible: the same split must always
    produce the same verdict.
    """
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    idx = np.arange(len(y_true))
    diffs = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        ys = y_true[s]
        if len(np.unique(ys)) < 2:
            continue
        diffs.append(roc_auc_score(ys, proba[s]) - roc_auc_score(ys, baseline_proba[s]))
    if len(diffs) < n // 2:
        raise ValueError(
            "Too few usable bootstrap replicates to form a confidence interval. "
            "Your validation set is too small or too imbalanced to support this gate."
        )
    d = np.sort(diffs)
    return float(np.quantile(d, alpha / 2)), float(np.quantile(d, 1 - alpha / 2))

def top_fraction_mask(proba: np.ndarray, fraction: float = 0.10) -> np.ndarray:
    """Select an exact contact budget, resolving score ties by stable row order."""
    proba = np.asarray(proba)
    if proba.ndim != 1 or len(proba) == 0 or not np.isfinite(proba).all():
        raise ValueError("Expected a nonempty vector of finite prediction scores")
    if not 0 < fraction <= 1:
        raise ValueError("Contact fraction must be in (0, 1]")
    count = max(1, int(np.ceil(len(proba) * fraction)))
    chosen = np.argsort(-proba, kind="stable")[:count]
    mask = np.zeros(len(proba), dtype=bool)
    mask[chosen] = True
    return mask

def evaluate_model(model: xgb.Booster,
                   X_val: np.ndarray,
                   y_val: np.ndarray,
                   baseline_proba: np.ndarray) -> dict:
    """
    Evaluate the trained model against required thresholds.
    Returns a metrics dict. Raises ValueError if thresholds are not met.
    """
    dval = xgb.DMatrix(X_val, feature_names=FEATURE_COLUMNS)
    y_pred_proba = model.predict(dval)

    auc_roc = roc_auc_score(y_val, y_pred_proba)

    # Precision and recall @ top 10%
    top10_mask = top_fraction_mask(y_pred_proba)
    precision_top10 = y_val[top10_mask].mean() if top10_mask.sum() > 0 else 0.0
    recall_top10 = y_val[top10_mask].sum() / y_val.sum() if y_val.sum() > 0 else 0.0

    # Baseline: a model trained on days_since_last_purchase ALONE.
    #
    # This used to be `np.full_like(y_pred_proba, y_val.mean())` - a constant
    # prediction, whose AUC is exactly 0.5 by definition. Beating a coin flip
    # is not evidence that your feature engineering did anything, and it is not
    # what Lab 3 asks for. The comparison that matters is against recency,
    # because recency is the rule the business already has for free.
    #
    baseline_auc = roc_auc_score(y_val, baseline_proba)
    auc_vs_baseline = auc_roc - baseline_auc

    lift_ci_low, lift_ci_high = bootstrap_lift_ci(
        y_val, y_pred_proba, baseline_proba)

    metrics = {
        "auc_roc": round(float(auc_roc), 4),
        "precision_top10": round(float(precision_top10), 4),
        "recall_top10": round(float(recall_top10), 4),
        "auc_vs_baseline": round(float(auc_vs_baseline), 4),
        "baseline_auc": round(float(baseline_auc), 4),
        "lift_ci_low": round(float(lift_ci_low), 4),
        "lift_ci_high": round(float(lift_ci_high), 4),
        "positive_rate_val": round(float(y_val.mean()), 4),
        "n_val_samples": int(len(y_val)),
        "n_val_positives": int(y_val.sum()),
        "top10_selected_count": int(top10_mask.sum()),
        "top10_true_positives": int(y_val[top10_mask].sum()),
        "bootstrap_replicates": BOOTSTRAP_N,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "confusion_threshold": 0.5,
        "xgboost_version": xgb.__version__,
        "eval_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\n── Evaluation Results ──────────────────────────────")
    failures = []
    for metric, threshold in EVAL_THRESHOLDS.items():
        value = metrics[metric]
        status = "PASS" if value >= threshold else "FAIL"
        print(f"  {metric:25s}: {value:.4f}  (threshold: {threshold:.4f})  {status}")
        if value < threshold:
            failures.append(f"{metric}={value:.4f} < {threshold}")

    # The baseline gate: the interval must exclude zero.
    ci_status = "PASS" if lift_ci_low > 0 else "FAIL"
    print(f"  {'auc_lift 95% CI':25s}: [{lift_ci_low:.4f}, {lift_ci_high:.4f}]"
          f"  (must exclude 0)  {ci_status}")
    if lift_ci_low <= 0:
        failures.append(
            f"auc_lift 95% CI [{lift_ci_low:.4f}, {lift_ci_high:.4f}] includes "
            f"zero - no evidence the model beats the recency-only baseline")

    if failures:
        raise ValueError(
            f"Model failed evaluation thresholds: {'; '.join(failures)}. "
            f"Do not promote to Model Registry."
        )

    print("  All thresholds passed")

    return metrics

def evaluate_slices(model: xgb.Booster,
                    X_val: np.ndarray,
                    y_val: np.ndarray,
                    slice_column: pd.Series) -> dict:
    """
    Evaluate model performance by slice (e.g., loyalty_tier, age_band).
    Flag slices where recall@10% drops more than 10pp below aggregate.

    Recall uses the same global top-10% contact list for every tier.
    Small-sample flags are descriptive, not an additional grading gate.
    """
    dval = xgb.DMatrix(X_val, feature_names=FEATURE_COLUMNS)
    y_pred_proba = model.predict(dval)
    y_val = np.asarray(y_val)
    tiers = np.asarray(slice_column)
    if len(tiers) != len(y_val) or pd.isna(tiers).any():
        raise ValueError("Every validation customer needs an aligned loyalty tier")
    contact_mask = top_fraction_mask(y_pred_proba)
    aggregate_recall = float(y_val[contact_mask].sum() / y_val.sum())

    slice_results = {}
    for slice_value in sorted(np.unique(tiers)):
        mask = tiers == slice_value
        n = int(mask.sum())
        positives = int(y_val[mask].sum())
        negatives = n - positives
        selected = mask & contact_mask
        true_positives = int(y_val[selected].sum())
        auc_value = float(roc_auc_score(y_val[mask], y_pred_proba[mask])) if min(positives, negatives) else None
        recall = float(true_positives / positives) if positives else None
        too_small = n < 100 or min(positives, negatives) < 30
        slice_results[str(slice_value)] = {
            "tier": str(slice_value), "n": n, "positives": positives,
            "negatives": negatives, "auc": auc_value, "recall": recall,
            "selected": int(selected.sum()), "true_positives": true_positives,
            "too_small": too_small,
            "too_small_rule": "n < 100 or fewer than 30 examples in either class",
            "recall_below_aggregate_10pp": bool(recall is not None and recall < aggregate_recall - 0.10),
        }
    print("\nLoyalty-tier evaluation (global top-10% contact policy):")
    print(pd.DataFrame(slice_results.values())[["tier", "n", "positives", "auc", "recall", "too_small"]].to_string(index=False))

    return slice_results

LABEL = LABEL_COLUMN


def train(df: pd.DataFrame, seed: int = 42):
    """Train, evaluate and return the exact booster checked by CI."""
    if SLICE_COLUMN not in df:
        raise ValueError("Training requires aligned loyalty_tier values")
    if "customer_id" in df:
        df = df.sort_values("customer_id").reset_index(drop=True)
    X, y = preprocess_features(df)
    tiers = df[SLICE_COLUMN].to_numpy(dtype=object)
    X_train, X_val, y_train, y_val, _, tier_val = train_test_split(
        X, y, tiers, test_size=0.30, random_state=seed, stratify=y)
    args = SimpleNamespace(max_depth=6, eta=0.1, num_round=200,
                           min_child_weight=5, subsample=0.8,
                           colsample_bytree=0.8, scale_pos_weight=None, seed=seed)
    model = train_model(X_train, y_train, X_val, y_val, args)
    baseline = train_recency_baseline(X_train, y_train, X_val, seed=seed)
    metrics = evaluate_model(model, X_val, y_val, baseline)
    metrics["slices"] = evaluate_slices(model, X_val, y_val, tier_val)
    metrics["split_seed"] = seed
    metrics["resolved_scale_pos_weight"] = args.resolved_scale_pos_weight
    metrics["baseline_auc_roc"] = metrics["baseline_auc"]
    return model, metrics

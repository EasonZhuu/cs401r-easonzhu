"""Loyalty-tier recall is visible to the approver; a large gap is nonblocking."""
import json
import os
from pathlib import Path
import warnings
import pytest


@pytest.fixture(scope="module")
def tier_metrics():
    path = Path(os.environ.get("EVAL_METRICS_PATH", "/tmp/eval_metrics.json"))
    if not path.is_file():
        pytest.fail(f"Fairness evidence missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))["slices"]


def test_highest_and_lowest_tiers_have_real_evaluation(tier_metrics):
    for tier in ("Bronze", "Platinum"):
        stats = tier_metrics[tier]
        assert stats["n"] > 0 and stats["positives"] > 0
        assert 0 <= stats["recall"] <= 1
        assert stats["recall"] == pytest.approx(stats["true_positives"] / stats["positives"])


def test_recall_gap_is_reported_without_blocking(tier_metrics):
    low, high = (tier_metrics[t]["recall"] for t in ("Bronze", "Platinum"))
    gap = abs(high - low)
    warnings.warn(f"fairness Bronze recall={low:.4f}; Platinum recall={high:.4f}; "
                  f"gap={gap:.4f}; threshold=0.10; flagged={gap > 0.10}", UserWarning)

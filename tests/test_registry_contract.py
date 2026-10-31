"""Registry gate behavior is testable without an AWS account or hardcoded champion."""
import io
import json
import pytest
from models.churn.registry import champion_from_registry, regresses


class Registry:
    def __init__(self, empty=False):
        self.empty = empty

    def list_model_packages(self, **kwargs):
        assert kwargs["ModelApprovalStatus"] == "Approved"
        assert kwargs["SortOrder"] == "Descending" and kwargs["SortBy"] == "CreationTime"
        return {"ModelPackageSummaryList": [] if self.empty else [{"ModelPackageArn": "champion"}]}

    def describe_model_package(self, **kwargs):
        assert kwargs["ModelPackageName"] == "champion"
        return {"ModelPackageArn": "champion", "ModelPackageVersion": 7,
                "ModelMetrics": {"ModelQuality": {"Statistics": {"S3Uri": "s3://bucket/metrics.json"}}}}


class Storage:
    def get_object(self, **kwargs):
        assert kwargs == {"Bucket": "bucket", "Key": "metrics.json"}
        return {"Body": io.BytesIO(json.dumps({"auc_roc": 0.75}).encode())}


def test_newest_approved_metrics_are_loaded():
    champion = champion_from_registry(Registry(), Storage())
    assert champion["version"] == 7 and champion["auc"] == 0.75


def test_no_approved_champion_is_distinct_from_read_error():
    assert champion_from_registry(Registry(empty=True), Storage()) is None


def test_s3_failure_is_not_silently_skipped():
    class BrokenStorage:
        def get_object(self, **kwargs):
            raise RuntimeError("S3 unavailable")
    with pytest.raises(RuntimeError, match="S3 unavailable"):
        champion_from_registry(Registry(), BrokenStorage())


@pytest.mark.parametrize("candidate,expected", [(0.73, False), (0.7299, True), (0.76, False)])
def test_regression_boundary(candidate, expected):
    assert regresses(candidate, 0.75) is expected


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -0.01, 1.01])
def test_invalid_auc_cannot_pass_regression(invalid):
    with pytest.raises(ValueError, match="finite probability"):
        regresses(invalid, 0.75)

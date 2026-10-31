"""Read the newest Approved champion without hiding Registry or S3 failures."""
import json
import math
from urllib.parse import urlparse


def regresses(candidate_auc, champion_auc, tolerance=0.02):
    for name, value in (("candidate", candidate_auc), ("champion", champion_auc)):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} AUC must be a finite probability")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Regression tolerance must be finite and nonnegative")
    return candidate_auc < champion_auc - tolerance


def champion_from_registry(sm=None, s3=None, group="northstar-churn-models"):
    if sm is None or s3 is None:
        import boto3
        sm = sm if sm is not None else boto3.client("sagemaker")
        s3 = s3 if s3 is not None else boto3.client("s3")
    packages = sm.list_model_packages(
        ModelPackageGroupName=group, ModelApprovalStatus="Approved",
        SortBy="CreationTime", SortOrder="Descending", MaxResults=1,
    )["ModelPackageSummaryList"]
    if not packages:
        return None
    package = sm.describe_model_package(ModelPackageName=packages[0]["ModelPackageArn"])
    uri = package["ModelMetrics"]["ModelQuality"]["Statistics"]["S3Uri"]
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ValueError(f"Invalid champion metrics S3 URI: {uri}")
    with s3.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))["Body"] as body:
        metrics = json.load(body)
    auc = float(metrics["auc_roc"])
    if not math.isfinite(auc) or not 0 <= auc <= 1:
        raise ValueError("Champion AUC must be a finite probability")
    return {"version": package["ModelPackageVersion"], "auc": auc,
            "arn": package["ModelPackageArn"], "metrics_uri": uri}

"""Register an already evaluated model, without training or approving it."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
import mlflow

GROUP = "northstar-churn-models"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def register_model(model_dir, metrics, lineage, bucket, output_dir,
                   mlflow_arn, region="us-east-1"):
    """Validate the MLflow chain, upload a reproducible bundle, and read back the version."""
    model_dir, output_dir = Path(model_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if digest(model_dir / "model.xgb") != lineage["model_sha256"]:
        raise ValueError("Model file differs from the evaluated model")
    if not (metrics["precision_top10"] >= 0.5 and metrics["recall_top10"] >= 0.25
            and metrics["lift_ci_low"] > 0):
        raise ValueError("The evaluated model does not pass the course gates")
    if metrics["xgboost_version"] != "3.2.0" or lineage["xgboost_version"] != "3.2.0":
        raise ValueError("This bundle targets the official XGBoost 3.2 runtime")
    mlflow.set_tracking_uri(mlflow_arn)
    tracking = mlflow.MlflowClient()
    run = tracking.get_run(lineage["mlflow_run_id"])
    if run.info.status != "FINISHED":
        raise ValueError("The selected MLflow run must be FINISHED")
    for key, value in metrics.items():
        if isinstance(value, (int, float)) and run.data.metrics.get(key) != float(value):
            raise ValueError(f"Metric differs from MLflow: {key}")
    if run.data.tags.get("athena_query_execution_id") != lineage["athena_query_execution_id"]:
        raise ValueError("MLflow run refers to a different Athena query")

    session = boto3.Session(region_name=region)
    config = Config(connect_timeout=5, read_timeout=30,
                    retries={"total_max_attempts": 3, "mode": "standard"})
    account = session.client("sts", config=config).get_caller_identity()["Account"]
    if account != mlflow_arn.split(":")[4] or bucket != f"northstar-dev-data-{account}":
        raise ValueError("Use the same account and original NorthStar data bucket")
    sm = session.client("sagemaker", config=config)
    s3 = session.client("s3", config=config)
    # Region account mapping comes from the installed SDK; the newer tag comes
    # from AWS's current available-images reference and is checked in ECR.
    from sagemaker import image_uris
    registry = image_uris.config_for_framework("xgboost")["inference"]["versions"]["1.7-1"]["registries"][region]
    images = session.client("ecr", config=config).batch_get_image(
        registryId=registry, repositoryName="sagemaker-xgboost", imageIds=[{"imageTag": "3.2-0"}])
    if len(images["images"]) != 1 or images.get("failures"):
        raise ValueError("The official XGBoost 3.2-0 image is unavailable in this region")
    image_id = images["images"][0]["imageId"]
    image = f"{registry}.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost@{image_id['imageDigest']}"

    handler = Path(__file__).resolve().parents[1] / "inference/churn/inference.py"
    members = {
        "model.xgb": (model_dir / "model.xgb").read_bytes(),
        "model_metadata.json": (model_dir / "model_metadata.json").read_bytes(),
        "evaluation_metrics.json": (json.dumps(metrics, indent=2) + "\n").encode(),
        "training-lineage.json": (json.dumps(lineage, indent=2) + "\n").encode(),
        "code/inference.py": handler.read_bytes(),
    }
    archive = model_dir / "model.tar.gz"
    with archive.open("wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as tar:
            for name, data in sorted(members.items()):
                item = tarfile.TarInfo(name)
                item.size, item.mode, item.mtime = len(data), 0o644, 0
                tar.addfile(item, io.BytesIO(data))
    archive_sha = digest(archive)
    prefix = f"artifacts/lab3/churn/{lineage['mlflow_run_id']}/{archive_sha}"
    key = f"{prefix}/model.tar.gz"
    transfer = TransferConfig(multipart_threshold=64 * 1024 * 1024)
    s3.upload_file(str(archive), bucket, key, Config=transfer)
    downloaded = model_dir / "registry-readback.tar.gz"
    s3.download_file(bucket, key, str(downloaded), Config=transfer)
    if digest(downloaded) != archive_sha:
        raise ValueError("Uploaded bundle differs from the local archive")
    metrics_key = f"{prefix}/evaluation_metrics.json"
    s3.put_object(Bucket=bucket, Key=metrics_key, Body=members["evaluation_metrics.json"], ContentType="application/json")

    groups = sm.get_paginator("list_model_package_groups").paginate(NameContains=GROUP)
    if not any(g["ModelPackageGroupName"] == GROUP for page in groups for g in page["ModelPackageGroupSummaryList"]):
        sm.create_model_package_group(ModelPackageGroupName=GROUP,
                                      ModelPackageGroupDescription="NorthStar churn models for CS 401R")
    metadata = {key: str(value) for key, value in metrics.items()}
    metadata.update({"mlflow_run_id": lineage["mlflow_run_id"],
                     "athena_query_execution_id": lineage["athena_query_execution_id"],
                     "model_sha256": lineage["model_sha256"], "bundle_sha256": archive_sha,
                     "training_source_sha256": lineage["training_source_sha256"],
                     "inference_source_sha256": digest(handler)})
    request = {
        "ModelPackageGroupName": GROUP,
        "ModelPackageDescription": "Evaluated local XGBoost 3.2.0 churn model; manual approval required",
        "ModelApprovalStatus": "PendingManualApproval",
        "InferenceSpecification": {
            "Containers": [{"Image": image, "ModelDataUrl": f"s3://{bucket}/{key}",
                            "Framework": "XGBOOST", "FrameworkVersion": "3.2.0",
                            "Environment": {"SAGEMAKER_PROGRAM": "inference.py",
                                            "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code"}}],
            "SupportedContentTypes": ["application/json", "text/csv"],
            "SupportedResponseMIMETypes": ["application/json"],
        },
        "ModelMetrics": {"ModelQuality": {"Statistics": {
            "ContentType": "application/json", "S3Uri": f"s3://{bucket}/{metrics_key}"}}},
        "CustomerMetadataProperties": metadata,
        "ClientToken": hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()[:32],
    }
    write_json(output_dir / "model-registration-request.json", request)
    created = sm.create_model_package(**request)
    arn = created["ModelPackageArn"]
    write_json(output_dir / "model-registration-receipt.json", created)
    for attempt in range(30):
        described = sm.describe_model_package(ModelPackageName=arn)
        if described["ModelPackageStatus"] == "Completed":
            break
        if described["ModelPackageStatus"] == "Failed":
            raise RuntimeError(f"Model registration failed: {described.get('ModelPackageStatusDetails')}")
        time.sleep(2)
    else:
        raise TimeoutError(f"Registration still pending: {arn}")
    if described["ModelApprovalStatus"] != "PendingManualApproval":
        raise ValueError("Unexpected approval status")
    if described["CustomerMetadataProperties"] != metadata:
        raise ValueError("Registry metrics or lineage differ from the evaluated run")
    if described["InferenceSpecification"]["Containers"][0]["ModelDataUrl"] != f"s3://{bucket}/{key}":
        raise ValueError("Registry points to a different model bundle")
    write_json(output_dir / "model-registry.json", described)
    tracking.set_tag(lineage["mlflow_run_id"], "model_package_arn", arn)
    tracking.set_tag(lineage["mlflow_run_id"], "model_approval_status", "PendingManualApproval")
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "model_package_arn": arn, "model_package_version": described["ModelPackageVersion"],
              "status": described["ModelPackageStatus"], "approval_status": described["ModelApprovalStatus"],
              "model_sha256": lineage["model_sha256"], "bundle_sha256": archive_sha,
              "bundle_s3_uri": f"s3://{bucket}/{key}", "official_image_tag": "3.2-0",
              "official_image_digest": image_id["imageDigest"], "metrics_match_mlflow_and_registry": True,
              "s3_bundle_readback_hash_matches": True, "endpoint_created": False}
    write_json(output_dir / "model-registration-check.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return arn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--artifacts-bucket", required=True)
    parser.add_argument("--mlflow-arn", required=True)
    parser.add_argument("--output-dir", default="docs/lab3-evidence")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    register_model(args.model_dir, json.loads(Path(args.metrics).read_text(encoding="utf-8")),
                   json.loads(Path(args.lineage).read_text(encoding="utf-8")),
                   args.artifacts_bucket, args.output_dir, args.mlflow_arn, args.region)


if __name__ == "__main__":
    main()

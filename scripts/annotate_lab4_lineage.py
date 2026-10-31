"""Attach verified final-green lineage; metadata values must be <=256 characters."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.parse import urlparse
import boto3
import pyarrow.parquet as pq


def location(uri):
    value = urlparse(uri)
    if value.scheme != "s3" or not value.netloc or not value.path.lstrip("/"):
        raise ValueError(f"Expected an S3 URI: {uri}")
    return value.netloc, value.path.lstrip("/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--package-arn", required=True)
    parser.add_argument("--data-uri", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", default="docs")
    args = parser.parse_args()
    session = boto3.Session(region_name=args.region)
    cb, sm, s3 = [session.client(name) for name in ("codebuild", "sagemaker", "s3")]
    builds = cb.batch_get_builds(ids=[args.build_id])["builds"]
    if len(builds) != 1 or builds[0]["buildStatus"] != "SUCCEEDED":
        raise ValueError("Lineage requires an actual successful CodeBuild build")
    build = builds[0]
    commit = build["resolvedSourceVersion"]
    package = sm.describe_model_package(ModelPackageName=args.package_arn)
    if not build["startTime"] <= package["CreationTime"] <= build["endTime"]:
        raise ValueError("Package was not created during the selected green build")
    uri = package["ModelMetrics"]["ModelQuality"]["Statistics"]["S3Uri"]
    bucket, key = location(uri)
    if f"/evaluations/{commit[:8]}/evaluation_metrics.json" not in "/" + key:
        raise ValueError("Registered metrics URI does not belong to this commit")
    with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
        metrics = json.load(body)
    if metrics["commit_sha"] != commit[:8]:
        raise ValueError("Metrics commit does not match the actual build")
    fields = ("auc_roc", "baseline_auc", "precision_top10", "recall_top10", "lift_ci_low", "lift_ci_high")
    if not all(math.isfinite(float(metrics[name])) for name in fields):
        raise ValueError("Lineage metrics must be finite")
    data_bucket, prefix = location(args.data_uri)
    objects, times, rows = [], set(), 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=data_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".parquet"):
                continue
            if obj["LastModified"] > build["startTime"]:
                raise ValueError("Features changed after the selected build started")
            response = s3.get_object(Bucket=data_bucket, Key=obj["Key"])
            with response["Body"] as body:
                table = pq.read_table(io.BytesIO(body.read()), columns=["event_time"])
            times.update(table["event_time"].to_pylist())
            rows += table.num_rows
            objects.append({"key": obj["Key"], "etag": obj["ETag"].strip('"'),
                            "version_id": response.get("VersionId"),
                            "last_modified": obj["LastModified"].isoformat()})
    if rows != 9999 or len(times) != 1:
        raise ValueError("Expected one coherent 9,999-customer feature snapshot")
    timestamp = next(iter(times))
    age = datetime.now(timezone.utc).timestamp() - timestamp
    if not math.isfinite(timestamp) or not -300 <= age <= 48 * 3600:
        raise ValueError("Cannot annotate stale or invalid feature timestamps")
    digest = hashlib.sha256(json.dumps(sorted(objects, key=lambda item: item["key"]),
                                      sort_keys=True).encode()).hexdigest()
    properties = {"training_data_s3_uri": args.data_uri,
                  "data_timestamp_utc": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                  "data_snapshot_sha256": digest, "code_commit_sha": commit,
                  "evaluation_metrics_s3_uri": uri, "build_id": args.build_id,
                  **{name: str(metrics[name]) for name in fields}}
    if any(len(value) > 256 for value in properties.values()):
        raise ValueError("SageMaker CustomerMetadataProperties value exceeds 256 characters")
    sm.update_model_package(ModelPackageArn=args.package_arn, CustomerMetadataProperties=properties)
    final = sm.describe_model_package(ModelPackageName=args.package_arn)
    final.pop("ResponseMetadata", None)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lab4-model-package.json").write_text(json.dumps(final, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "lab4-data-lineage.json").write_text(json.dumps({"data_uri": args.data_uri, "customers": rows,
        "event_time": timestamp, "manifest_sha256": digest, "objects": objects}, indent=2) + "\n", encoding="utf-8")
    print(f"Annotated package v{final['ModelPackageVersion']} from green commit {commit}; {rows} feature rows")


if __name__ == "__main__":
    main()

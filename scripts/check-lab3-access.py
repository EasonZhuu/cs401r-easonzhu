"""Check course-account access and Lab 3 prerequisites without changing resources."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", type=Path,
                        default=root / "docs/lab3-access-check.json")
    args = parser.parse_args()
    backend = (root / "infrastructure/environments/dev/backend.tf").read_text()
    match = re.search(r'bucket\s*=\s*"(northstar-tfstate-(\d{12}))"', backend)
    if not match:
        raise ValueError("Cannot determine the course account from backend.tf")
    state_bucket, expected_account = match.groups()
    config = Config(connect_timeout=5, read_timeout=30,
                    retries={"total_max_attempts": 2, "mode": "adaptive"})
    session = boto3.Session(region_name=args.region)
    clients = {service: session.client(service, config=config)
               for service in ("sts", "s3", "sagemaker", "glue", "iam",
                               "bedrock-runtime")}
    try:
        identity = clients["sts"].get_caller_identity()
    except ClientError as error:
        print(f"FAIL AWS identity: {error.response['Error']['Code']}")
        return 1
    if identity["Account"] != expected_account:
        raise RuntimeError("AWS account does not match the course Terraform backend")
    print("PASS AWS identity matches the course Terraform backend", flush=True)

    account = identity["Account"]
    bucket = f"northstar-dev-data-{account}"
    feature_group = "northstar-dev-customer-features"
    checks = [
        ("data_bucket", lambda: clients["s3"].head_bucket(Bucket=bucket)),
        ("state_bucket", lambda: clients["s3"].head_bucket(Bucket=state_bucket)),
        ("feature_group", lambda: clients["sagemaker"].describe_feature_group(
            FeatureGroupName=feature_group)),
        ("glue_database", lambda: clients["glue"].get_database(Name="northstar_dev")),
        ("ml_engineer_role", lambda: clients["iam"].get_role(
            RoleName="northstar-dev-MLEngineer")),
        ("data_engineer_role", lambda: clients["iam"].get_role(
            RoleName="northstar-dev-DataEngineer")),
    ]
    results = {}
    for name, request in checks:
        try:
            response = request()
        except ClientError as error:
            code = error.response["Error"]["Code"]
            missing = code in {"404", "NoSuchBucket", "ResourceNotFound",
                               "ResourceNotFoundException", "EntityNotFoundException",
                               "NoSuchEntity"}
            results[name] = {"status": "MISSING" if missing else "ERROR",
                             "error_code": code,
                             "message": error.response["Error"].get("Message", "")}
        else:
            results[name] = {"status": "PRESENT"}
            if name == "feature_group":
                results[name].update({
                    "feature_group_status": response["FeatureGroupStatus"],
                    "offline_store": response.get("OfflineStoreConfig", {}),
                })
        print(f"{results[name]['status']} {name}", flush=True)

    bedrock = clients["bedrock-runtime"]
    control = session.client("bedrock", config=config)
    try:
        control.get_use_case_for_model_access()
    except control.exceptions.ResourceNotFoundException:
        form_status = "NOT_SUBMITTED"
    else:
        form_status = "SUBMITTED"
    print(f"Anthropic use-case form: {form_status}", flush=True)
    bedrock_checks = {}
    try:
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json", accept="application/json",
            body=json.dumps({"inputText": "30 day return policy"}),
        )
        with response["body"] as body:
            payload = json.loads(body.read())
        dimensions = len(payload["embedding"])
        if dimensions != 1024:
            raise ValueError(f"Expected 1024 embedding dimensions, got {dimensions}")
        bedrock_checks["titan"] = {"status": "PASS", "dimensions": dimensions}
        print(f"PASS Titan embeddings: dim={dimensions}", flush=True)
    except ClientError as error:
        bedrock_checks["titan"] = {"status": "FAIL", "error": error.response["Error"]}
        print(f"FAIL Titan embeddings: {error.response['Error']['Code']}", flush=True)

    try:
        response = bedrock.converse(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            messages=[{"role": "user", "content": [{"text": "Reply with OK"}]}],
            inferenceConfig={"maxTokens": 10},
        )
        answer = "".join(block.get("text", "")
                         for block in response["output"]["message"]["content"]).strip()
        if not answer:
            raise ValueError("Claude returned no text")
        bedrock_checks["haiku"] = {"status": "PASS", "response": answer,
                                   "usage": response.get("usage", {})}
        print(f"PASS Claude Haiku 4.5: {answer!r}", flush=True)
    except ClientError as error:
        bedrock_checks["haiku"] = {"status": "FAIL", "error": error.response["Error"]}
        print(f"FAIL Claude Haiku 4.5: {error.response['Error']['Code']}", flush=True)

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "account": account,
        "identity_arn": identity["Arn"],
        "data_bucket": bucket,
        "feature_group": feature_group,
        "resources": results,
        "bedrock": bedrock_checks,
        "anthropic_use_case_form": form_status,
        "training_resources_present": all(results[name]["status"] == "PRESENT"
            for name in ("data_bucket", "feature_group", "glue_database",
                         "ml_engineer_role", "data_engineer_role")),
        "cloud_resources_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n",
                           encoding="utf-8")
    print(f"Saved {args.output}", flush=True)
    # A missing resource is a completed observation, not a successful prerequisite.
    return 0 if (all(x["status"] == "PASS" for x in bedrock_checks.values())
                 and all(x["status"] != "ERROR" for x in results.values())) else 1


if __name__ == "__main__":
    raise SystemExit(main())

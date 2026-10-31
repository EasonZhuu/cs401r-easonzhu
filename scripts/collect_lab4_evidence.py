"""Capture real Lab4 evidence before deleting the resources that hold it."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import boto3


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def registry(sm):
    packages = []
    paginator = sm.get_paginator("list_model_packages")
    for page in paginator.paginate(ModelPackageGroupName="northstar-churn-models",
                                   SortBy="CreationTime", SortOrder="Descending"):
        for item in page["ModelPackageSummaryList"]:
            package = sm.describe_model_package(ModelPackageName=item["ModelPackageArn"])
            package.pop("ResponseMetadata", None)
            packages.append(package)
    return packages


def build_evidence(codebuild, logs, build_id):
    builds = codebuild.batch_get_builds(ids=[build_id])["builds"]
    if len(builds) != 1:
        raise ValueError(f"Build not found: {build_id}")
    build = builds[0]
    stream = build["logs"]
    events = []
    for page in logs.get_paginator("filter_log_events").paginate(
            logGroupName=stream["groupName"], logStreamNames=[stream["streamName"]]):
        events.extend(page["events"])
    if not events:
        raise ValueError(f"Build log is empty: {build_id}")
    text = "".join(event["message"] for event in events)
    summary = {name: build.get(name) for name in
               ("id", "buildStatus", "sourceVersion", "resolvedSourceVersion", "startTime", "endTime", "phases")}
    summary["logs"] = stream
    summary["pytest_summaries"] = re.findall(r"[^\n]*(?:passed|failed|skipped|deselected)[^\n]*", text)
    return summary, text


def export_mlflow(uri, out):
    import mlflow
    if ":mlflow-app/" not in uri:
        raise ValueError("Expected the existing serverless MLflow App ARN")
    mlflow.set_tracking_uri(uri)
    runs = mlflow.search_runs(experiment_names=["northstar-churn"], max_results=10000)
    hyperparameters = ["params."+name for name in ("max_depth", "eta", "num_round", "min_child_weight",
                       "subsample", "colsample_bytree", "scale_pos_weight", "seed")]
    columns = [name for name in hyperparameters if name in runs]
    valid = runs.loc[(runs["status"] == "FINISHED") & runs["metrics.auc_roc"].between(0, 1)]
    params = valid[columns]
    if params.empty or len(params.drop_duplicates()) < 3:
        raise ValueError("Need at least three distinct logged hyperparameter combinations")
    (out / "lab4-mlflow-runs.txt").write_text(
        "Tracking URI: " + uri + "\nExported at UTC: " + datetime.now(timezone.utc).isoformat()
        + "\nThese are existing experiment runs; creation time identifies their lab of origin.\n\n"
        + runs.to_string(index=False) + "\n", encoding="utf-8")
    print(f"Exported {len(runs)} MLflow runs, {len(params.drop_duplicates())} parameter combinations")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", default="docs")
    parser.add_argument("--snapshot", choices=["BEFORE", "AFTER FAILED RUN", "AFTER REVERT"])
    parser.add_argument("--build-id")
    parser.add_argument("--green-build-id")
    parser.add_argument("--failed-build-id")
    parser.add_argument("--final-package-arn")
    parser.add_argument("--mlflow-app-arn")
    parser.add_argument("--mlflow-only", action="store_true")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.mlflow_only:
        if not args.mlflow_app_arn:
            parser.error("--mlflow-only requires --mlflow-app-arn")
        export_mlflow(args.mlflow_app_arn, out)
        return
    session = boto3.Session(region_name=args.region)
    sm, cw, logs, cb = [session.client(service) for service in
                        ("sagemaker", "cloudwatch", "logs", "codebuild")]
    packages = registry(sm)
    alarm = cw.describe_alarms(AlarmNames=["northstar-ci-build-failure"])["MetricAlarms"]
    if len(alarm) != 1:
        raise ValueError("Expected the deployed build-failure alarm before collecting evidence")
    history = []
    for page in cw.get_paginator("describe_alarm_history").paginate(AlarmName="northstar-ci-build-failure"):
        history.extend(page["AlarmHistoryItems"])
    sns = session.client("sns")
    account = session.client("sts").get_caller_identity()["Account"]
    topic = f"arn:aws:sns:{args.region}:{account}:northstar-model-approvals"
    subscriptions = []
    for page in sns.get_paginator("list_subscriptions_by_topic").paginate(TopicArn=topic):
        for subscription in page["Subscriptions"]:
            if subscription["Protocol"] in ("email", "email-json"):
                subscription["Endpoint"] = "[redacted email]"
            subscriptions.append(subscription)
    if args.snapshot:
        value = {"label": args.snapshot, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                 "registry": [{"version": p["ModelPackageVersion"], "arn": p["ModelPackageArn"],
                               "status": p["ModelApprovalStatus"]} for p in packages],
                 "alarm": alarm, "alarm_history": history, "subscriptions": subscriptions}
        if args.build_id:
            value["build"], _ = build_evidence(cb, logs, args.build_id)
        with (out / "lab4-failure-demo.txt").open("a", encoding="utf-8") as stream:
            stream.write(f"\n=== {args.snapshot} ===\n" + json.dumps(value, indent=2, default=str) + "\n")
        print(f"Captured {args.snapshot}; latest package version={max((p['ModelPackageVersion'] for p in packages), default=None)}")
        return
    write_json(out / "lab4-model-registry.json", packages)
    if args.final_package_arn:
        final = sm.describe_model_package(ModelPackageName=args.final_package_arn)
        final.pop("ResponseMetadata", None)
        write_json(out / "lab4-model-package.json", final)
    executions = []
    pipeline = session.client("codepipeline")
    for page in pipeline.get_paginator("list_pipeline_executions").paginate(pipelineName="northstar-pipeline"):
        executions.extend(page["pipelineExecutionSummaries"])
    model_executions = []
    for page in sm.get_paginator("list_pipeline_executions").paginate(PipelineName="northstar-churn-pipeline"):
        model_executions.extend(page["PipelineExecutionSummaries"])
    all_builds = []
    for page in cb.get_paginator("list_builds_for_project").paginate(projectName="northstar-ci", sortOrder="ASCENDING"):
        for build_id in page["ids"]:
            summary, content = build_evidence(cb, logs, build_id)
            all_builds.append(summary)
            if build_id == args.green_build_id:
                (out / "lab4-build-green.log").write_text(content, encoding="utf-8")
            if build_id == args.failed_build_id:
                (out / "lab4-build-failed.log").write_text(content, encoding="utf-8")
    write_json(out / "lab4-pipeline-runs.txt", {"codepipeline": executions,
               "codebuild": all_builds, "sagemaker": model_executions,
               "alarm_history": history, "subscriptions": subscriptions})
    if args.mlflow_app_arn:
        export_mlflow(args.mlflow_app_arn, out)
    statuses = {build["id"]: build["buildStatus"] for build in all_builds}
    for build_id, expected in ((args.green_build_id, "SUCCEEDED"), (args.failed_build_id, "FAILED")):
        if build_id and statuses.get(build_id) != expected:
            raise ValueError(f"Expected {expected} for {build_id}; found {statuses.get(build_id)}")
    print(f"Collected {len(all_builds)} builds and {len(packages)} model packages into {out}")


if __name__ == "__main__":
    main()

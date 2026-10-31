"""Read-only readiness report. Never create resources or launch jobs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--connection-arn", required=True)
    parser.add_argument("--request-id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    session = boto3.Session(region_name=args.region)
    sts, sq, connections, ec2, glue = [session.client(name) for name in
                                      ("sts", "service-quotas", "codeconnections", "ec2", "glue")]
    quota = sq.get_service_quota(ServiceCode="sagemaker", QuotaCode="L-29688C85")["Quota"]
    connection = connections.get_connection(ConnectionArn=args.connection_arn)["Connection"]
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": ["northstar-dev-vpc"]}])["Vpcs"]
    if len(vpcs) != 1:
        raise ValueError("Expected exactly one northstar-dev-vpc; cannot verify NAT ownership")
    nats = [nat for page in ec2.get_paginator("describe_nat_gateways").paginate(
        Filter=[{"Name": "vpc-id", "Values": [vpcs[0]["VpcId"]]}])
        for nat in page["NatGateways"] if nat["State"] != "deleted"]
    job = glue.get_job(JobName="northstar-dev-feature-engineer")["Job"]
    result = {"captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "account": sts.get_caller_identity()["Account"], "region": args.region,
              "connection_status": connection["ConnectionStatus"],
              "spot_quota": quota["Value"], "training_instance_count": 1,
              "ready_for_spot_training": quota["Value"] >= 1 and connection["ConnectionStatus"] == "AVAILABLE",
              "nat_gateways": [{"id": nat["NatGatewayId"], "state": nat["State"]} for nat in nats],
              "glue_shared_module": job["DefaultArguments"].get("--extra-py-files")}
    if args.request_id:
        request = sq.get_requested_service_quota_change(RequestId=args.request_id)["RequestedQuota"]
        result["quota_request"] = {key: request.get(key) for key in
                                    ("Id", "Status", "CaseId", "DesiredValue", "LastUpdated")}
    Path(args.output).write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

# Lab4 execution runbook

Status: local implementation ready; Spot quota is now ten and cloud validation is underway.
Do not label this runbook itself as proof that any step ran.

## Before creating hourly resources

Run `scripts/lab4_preflight.py` with the authorized connection ARN and quota
request ID recorded in the private course execution record. Require AVAILABLE
and applied `ml.m5.large` managed Spot quota >= 1 in us-east-1. The request asks
for five because the API rejected one as below its published default; the job
uses exactly one instance. Do not switch instance types to bypass this blocker.

1. Review a **new** Terraform plan with `enable_nat_gateway=true`. Earlier plans
   are stale after the non-NAT prerequisites apply. Confirm only intended
   resources change; apply and start recording NAT/EIP lifetime.
2. Start `northstar-dev-feature-engineer` once. Require SUCCEEDED; download its
   new processed/features outputs and use `scripts/validate_lab4_features.py`.
   Run the complete data suite, including freshness. Never edit event_time.
3. Commit the implementation, fast-forward the personal repository's main and
   push. Verify GitHub main matches the intended SHA. Keep instructor materials
   and private notes out of this repository.
4. Create a separate versioned CI artifacts bucket with public access blocked,
   AES256 server-side encryption, and ownership enforcement. Keep it separate
   from the Terraform data bucket.
5. Deploy `pipeline.yaml` as `northstar-cicd`, with GitHubOwner=EasonZhuu,
   GitHubRepo=cs401r-easonzhu, GitHubBranch=main, the authorized connection ARN,
   artifacts bucket and existing MLEngineer role ARN. Use
   `CAPABILITY_NAMED_IAM`. Review the change set before executing.
6. Subscribe the user's confirmed email to `northstar-model-approvals`;
   the user confirms the SNS subscription. Do not publish email addresses in
   repository evidence. Do not deploy a model endpoint.

## Three actual runs

* First green: require the CodeBuild build itself SUCCEEDED, all four test types
  executed, SageMaker execution SUCCEEDED and package PendingManualApproval.
  The initial champion test may skip only if no Approved champion exists.
  Approve this green package as the initial champion.
* BEFORE: wait for alarm OK and capture Registry versions/status, alarm history,
  subscriptions and the green build with `collect_lab4_evidence.py --snapshot BEFORE`.
* Failure: add a clearly named, deliberately failing PRE_BUILD feature assertion,
  commit and push main. Save its SHA and complete log. Require PRE_BUILD FAILED,
  no training execution and no new model version. Wait for the actual alarm
  transition and received notification email; capture AFTER FAILED RUN and an
  original email screenshot including receipt time, with address redacted if needed.
* Revert: `git revert` the failure commit, push main and require final CodeBuild
  SUCCEEDED. Champion regression must now PASSED and show version/AUC warning.
  Capture AFTER REVERT after alarm returns OK. Keep both failure and revert in history.

## Final lineage and evidence

Update the final green model package's CustomerMetadataProperties with actual
training data S3 URI, dataset timestamp, exact commit SHA and metrics from that
run. Never use the local uncommitted training identifier as cloud lineage.
Export the full package, all Registry versions, builds and pipeline executions,
green/failed logs and existing MLflow App search_runs table with
`scripts/collect_lab4_evidence.py`. Check IDs and nonempty outputs. SNS action
history is not email delivery evidence. Refresh the assessment from actual runs.

## Stop billing and handoff

Export evidence before removing resources. Delete the CI stack before the final
docs push so that documentation does not trigger another training run. Preserve
the role-owned cleanup order: Registry Approved packages must become Rejected
before deleting their artifacts; empty all versions/delete markers in the CI
bucket; follow the Lab2 teardown script after reviewing its exact targets.
Verify NAT gateways deleted, EIPs released, and no running Glue/training jobs or
endpoints. Save the cleanup results and measured resource lifetime.

The incremental cost target is USD 5, not a real-time hard cap. Pause new paid
jobs near that target and retain evidence before cleanup. AWS cost reporting can
lag. Final `lab4-submit` tag and Canvas URL submission require the user's final
confirmation; neither has been executed.

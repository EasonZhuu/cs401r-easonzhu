# Lab 4 XOps assessment

Implementation status: three real CI runs completed on 2026-10-31: green,
deliberate PRE_BUILD failure, and revert green. The final build passed 82 tests
with no skips, including a real Approved v2 champion comparison. Evidence was
exported before teardown. Grading tag and Canvas submission remain the owner's
final step.

## Pipeline Stage Mapping

I chose the provided AWS CodePipeline/CodeBuild stack because it connects the
existing Terraform-managed data platform to SageMaker without introducing another
runner or secret store. `pipeline.yaml` defines Source, Build and manual approval.
Inside Build, `buildspec.yml` maps the five logical phases as follows:

| Logical phase | Actual implementation |
| --- | --- |
| Test | PRE_BUILD downloads raw/processed/features and runs data, feature, boundary and Registry contract tests |
| Build | BUILD upserts and starts `northstar-churn-pipeline` |
| Train | SageMaker `TrainChurnModel` invokes `train_sagemaker.py` and `churn_model.train` on one managed Spot ml.m5.large |
| Evaluate | Training checks precision/recall/bootstrap lift; CodeBuild checks the actual artifact, Approved champion and loyalty slices |
| Register | `RegisterChurnModel` creates PendingManualApproval; a subsequent CodeBuild model-gate failure rejects that package |

Registration occurs before the CodeBuild artifact/regression gate in the provided
template. Therefore registration alone is not promotion. A PRE_BUILD failure
cannot train or register. Model serving is outside this lab; no endpoint is created.

## Champion-Challenger

The newest Approved package by creation time is the champion. Read its AUC from
the S3 object cited in ModelMetrics, never from a hardcoded constant. The candidate
must have Precision@top10 >= 0.50, Recall@top10 >= 0.25, paired-bootstrap 95% lift
CI lower bound > 0, and AUC >= champion AUC - 0.02. This last threshold is the
explicit numeric eligibility criterion for replacement; it tolerates two points
of AUC regression rather than asserting superiority. Missing Approved packages
allow bootstrap only; unreadable Registry/S3 data or invalid AUC must fail.
After all gates pass, a human approves the eligible package and reviews warnings.
Bronze/Platinum recall gap > 0.10 produces a warning, not an automatic rejection.
The final cloud gap is 0.3928 (Bronze 0.4404, Platinum 0.0476). Platinum has
only 21 positives, so its recall estimate needs cautious interpretation. The
candidate AUC 0.7775 equals champion v2 AUC 0.7775. The authorized operator
approved v3 after review; teardown changes Approved packages to Rejected before
deleting their backing artifacts. This is lifecycle cleanup, not a failed gate.

## Retraining Triggers

These are designs; the services below are not deployed or billed by this lab.

* Scheduled: EventBridge Scheduler `cron(0 9 ? * MON *)`, UTC, invokes a Lambda
  coordinator. It runs the Glue feature job, requires SUCCEEDED and freshness
  <= 48 hours, then starts the same tested pipeline through CodePipeline.
* Performance: a daily evaluation job joins scored customers with matured
  90-day holdout labels. It evaluates the latest 30 days of fully matured cohorts,
  requiring >= 1,000 labelled customers and both classes. Publish AUC to
  CloudWatch; AUC < 0.75 on two consecutive daily evaluations changes an alarm
  to ALARM. EventBridge invokes the same coordinator. Insufficient labels emit
  an insufficient-data signal, never a fabricated AUC. Deduplicate by cohort end
  date, allow one execution at a time, and impose a 24-hour cooldown. The
  coordinator refreshes features and uses the same gates and manual promotion.

## DataOps Maturity

Current level: Level 1, Repeatable. Terraform and Glue reproduce cleaning,
customer features, holdout labels, Parquet output and Feature Store ingestion.
The shared pandas module is distributed through `--extra-py-files`; hash
partitioning keeps each customer's transactions together. Boundary tests cover
empty customers, missing values and both window endpoints. The historical data
suite genuinely failed freshness; no timestamp was edited. A subsequent real
Glue run generated 9,999 feature rows and ingested 9,999 records. All eleven
features, labels and customer identities matched the previous Spark output;
only the processing timestamp changed. The refreshed data suite passed 28 tests.
Evidence is retained in `lab4-fresh-data-tests.xml`, both parity JSON files and
the build logs. Code-triggered validation is automated, but the upstream feature
refresh still required an operator. Scheduled ingestion, schema-change review
and source failure recovery have not been deployed. Therefore I do not claim
end-to-end Level 2 DataOps. The highest priority is the documented refresh
coordinator: run Glue, require success and freshness, then invoke the same CI.
Immutable dataset manifests, explicit ownership and monitoring of late inputs
would make that automation easier to operate and audit.

## MLOps Maturity

Current level: Level 2, Automated, within this lab's training and registration
scope. GitHub pushes actually invoked CodePipeline through WebhookV2, and
CodeBuild executed data, feature, model and fairness tests. The revert build
passed all 82 tests without a skip. It read Approved v2 metrics from S3 and
compared candidate AUC 0.7775 against champion AUC 0.7775. Precision was 0.7000,
recall 0.3182 and paired lift CI [0.0338, 0.0739]. The deliberate failure stopped
in PRE_BUILD, started no training and left Registry at v2. CloudWatch entered
ALARM and the actual notification email arrived at 21:09:54 UTC. Logs, three
snapshots and the original email screenshot preserve this sequence. Both Lab4
packages carry exact commits, data manifests and metrics; four existing MLflow
runs provide three parameter combinations. Approval remained an operator
decision; no serving endpoint was deployed. The 0.3928 tier recall gap remains
a visible limitation. Level 3 governance and monitored performance retraining
are not established by CI alone. The next investment is a production evaluation
loop using matured labels, a documented fairness review policy and durable
audit ownership. The proposed retraining triggers are designs, not deployed
drift detection.

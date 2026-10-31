# Lab 4 XOps assessment

Implementation status: local validation completed; applied Spot quota is now ten.
Cloud CI runs, champion approval, failure/revert evidence, final lineage and alarm
email remain pending. This is a working assessment, not a claim of completed CI.

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
The current local gap is approximately 0.2616 and Platinum has only 21 positives,
so its recall estimate needs cautious interpretation.

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

Current level: Level 1, Repeatable, using the course table: pipelines exist but
are manually triggered, with versioning and basic monitoring. The Glue jobs and
Terraform definitions already provide a reproducible path from raw transactions
to cleaned Parquet, customer features, holdout labels, and Feature Store records.
The Lab4 change makes `data/feature_engineering.py` the shared calculation module;
Glue distributes it through `--extra-py-files` instead of maintaining separate
Spark formulas. Evidence: `tests/test_data.py`, `tests/test_features.py`,
`tests/test_feature_boundaries.py`, and `docs/lab4-local-validation.json` record
independent boundaries and historical-output parity. All eleven features and
labels matched 9,999 customers from 157,627 processed rows. Running the complete
historical data suite intentionally exposed one stale-data failure; no timestamp
was edited to make that result green. This is evidence of enforcement locally,
not evidence that refreshed cloud data exists. Gap to Level 2, Automated: the
proposed code-triggered CI and scheduled refresh have not yet been demonstrated,
and cloud Glue execution of the new shared module is being verified before
the first CI run. Top priority investment: finish the real
CodePipeline data gate, refresh Glue output in the execution window, and retain
its timestamp and logs. Then deploy the documented Scheduler coordinator with
freshness enforcement and failure monitoring. Versioned inputs and a routine
schema-change review would make later investigations easier.

## MLOps Maturity

Current level: Level 1, Repeatable. Training is callable through the container
contract, the data split and baseline are reproducible, model artifacts include
separate metadata, and experiment tracking already exists. Evidence:
`models/churn/churn_model.py`, `tests/test_model.py`, `tests/test_fairness.py`, and
`docs/lab4-mlflow-runs.txt` show executable checks and four existing MLflow runs
with three distinct hyperparameter combinations. Local XGBoost 1.7 training and
newer-version artifact loading passed; precision was 0.6967, recall 0.3167, and
the paired lift confidence interval was [0.0382, 0.0750]. The tier warning remains
visible rather than being hidden by the aggregate metrics. Gap to Level 2,
Automated: no Lab4 cloud green/failure/revert sequence, real champion comparison,
or delivered alarm email has yet been verified. Configuration alone cannot
establish automatic operation. Top priority investment: obtain Spot quota,
execute and retain those runs, approve the initial champion, and attach final
lineage before teardown. Even after successful CI, Level 3, Governed, would
require operational audit trails and policy enforcement together with automated
retraining on monitored drift signals. The proposed triggers describe that next
step but do not constitute deployed drift detection or a closed production loop.

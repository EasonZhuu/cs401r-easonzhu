# Lab 3 verification and handoff

Track: A+B. See the executed notebook and the separate churn/RAG reports for actual results and limitations.

- Churn: AUC 0.7838, precision_top10 0.7133, recall_top10 0.3242; paired lift CI [0.0415, 0.0802]. The selected query, run and registered model agree. Registered version 1 remains PendingManualApproval.
- RAG: 48 policy sections, 1024-dimensional Titan vectors, exact FAISS and A/B/C query implementations. Four original cases were evaluated twice under six configurations (48 valid scored rows). The final controlled configuration is deliberately bounded and all five real-customer deliveries used policy-template fallback; raw LLM drafts and low RAGAS scores are retained.
- Notebook: six code cells completed sequentially in a new project-Python kernel, saved with outputs. The public reproduction command was also verified.
- Teacher evidence collector: **25 OK, 0 WARN, 0 FAIL** with Python UTF-8 mode. Evidence is exported in `docs/lab3-evidence/` before cleanup.
- Teacher Lab 3 teardown: all required checks OK. The MLflow App, model version and original data platform are retained.
- Temporary NAT internet egress: the reviewed Terraform plan removed only `module.vpc.aws_nat_gateway.this[0]`, its dedicated EIP, and private default route. Live readback found the NAT deleted and EIP absent, while the data bucket, Feature Group and MLflow App remain available. See `lab3-network-pause-check.json`.

The local ignored `infrastructure/environments/dev/cost-pause.auto.tfvars` now sets `enable_nat_gateway=false`. The next Glue job requiring private-subnet internet access needs it re-enabled and a reviewed Terraform apply. This pause does not mean that all reusable platform/storage resources have been destroyed or that the entire AWS account has no costs.

The design report is approximately 700 words. Five final input/output pairs and two observed failure cases with proposed fixes are in `lab3-evidence/track-b-examples.md`. Full raw draft records, judge checkpoints, repeated ranges and an actual judge-verdict diagnostic remain available for review.

The current course Canvas assignment is 1476009. Its live page requires the original repository URL and a pushed `lab3-submit` tag; the latest announcement remains October 14, and the October 12 RAGAS grading change is applied. The final browser submission receipt is kept in the course-local Lab 3 folder after tagging, rather than modifying the graded commit after submission.

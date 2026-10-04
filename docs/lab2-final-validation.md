# Lab 2 — Final Validation

Verified on 2026-10-03 America/Denver (2026-10-04 UTC), against AWS
account `173506956686` in `us-east-1` and the final submission working tree.

## Results

| Check | Result | Evidence |
|-------|--------|----------|
| Course resource, data-quality and deliverable verifier | 47 passed, 0 failed; exit code 0 | [Output](lab2-verify-output.txt) |
| Full processed, feature and offline-store audit | 74 passed, 0 failed; all 60 Parquet file hashes and raw CSV rechecked | [Audit](lab2-parquet-audit.md), [hash check](lab2-final-snapshot-hash-check.json) |
| Recursive Terraform formatting and dev/local validation | Passed; valid configuration, 0 errors and 0 warnings | Terraform CLI validation |
| Task 1 LocalStack validation | Fresh run passed; three IAM roles with policies, VPC, public/private subnets; NAT skipped | [Output](lab2-localstack-output.txt) |
| Latest-guide live network requirements | 8 passed, 0 failed; shared SageMaker group and specified Glue connection | [Live AWS checks](lab2-final-network-verification.json) |
| Post-apply Terraform plan | No changes; actual infrastructure matches the configuration | Read-only plan completed with exit code 0 |
| Local scripts match deployed scripts | SHA-256 matches for both S3 scripts; executable AST unchanged | [Hashes](lab2-deployed-script-hashes.json) |
| Updated official teardown script | Exact official download; four simulated guard cases passed, no AWS mutations | [Guard tests](lab2-teardown-guard-tests.json) |
| Repository structure and credential checks | 14 passed, 0 failed | [Report](lab2-repo-quality.json), [history scan](lab2-secrets-check.txt) |

The course verifier confirmed the private subnet, available NAT, SageMaker
Domain in `VpcOnly` mode, IAM boundaries, five lifecycle rules, catalog table,
successful Glue jobs, data-quality assertions, Feature Group definitions and
an online record with 16 fields. The independent audit covers all 157,627
processed transactions, 9,999 feature customers and 9,999 offline records for
the recorded ingestion event. Online records were sampled.

## Latest course alignment and AWS changes

The final network update applied **1 addition, 4 updates, 0 deletions**.
Both jobs now use `northstar-dev-vpc-connection`, which selects the private
subnet and `northstar-dev-sagemaker-sg`. The Domain shares this group; its
all-protocol self ingress enables worker communication. The old connection
and dedicated Glue group remain unused until approved lab teardown. A
Terraform `moved` block preserves ownership of that old connection.

The feature script's obsolete silent-drop explanation was corrected: a
value incompatible with Fractional `event_time` is rejected. Computation
logic is unchanged. A second apply synchronizes LF line endings in the two
S3 scripts; it changes no computation, job configuration or dataset.

The new network configuration was checked through live AWS APIs. Paid Glue
jobs were not restarted after the network update; successful run evidence
and the data audit refer to the previously completed batch.

All available genuine apply transcripts are consolidated in
`lab2-extend-output.txt`, preserving the original Domain creation. Initial
transform-job and Feature Group creation transcripts were not found in the
saved output. [Provenance](lab2-apply-log-provenance.md) records this gap;
current state, successful runs and final apply evidence remain available.
Three [CloudTrail creation events](lab2-creation-api-evidence.json) identify
Terraform and its AWS provider as the creating client.

## Windows execution and verification evidence

The verifier writes its tally with `newline="\n"`, fixing Windows CRLF
summary accounting without altering any course assertion. `.gitattributes`
keeps Bash and Python files in LF format for a functional fresh checkout.

For the recorded run, an external temporary copy replaced only its temporary
`rm -rf` with a retained-path message, honoring separate deletion approval.
All assertions were preserved. Downloaded files remain on D: in
`.tools/parquet-validation/verify-tmp/tmp.kw1E4SiQwF`. The raw transcript is
retained outside Git as `course-verifier-output-final.raw.txt`; the committed
log strips trailing alignment spaces only.

The final canonical verifier SHA-256 is `57c6abaad871ea6e02fcb0dfc7d824834f347e32c78646455f94cb64293db0d0`. Its LF-normalized
text is identical to the source used for the recorded verification run.
The existing Python runtime was reused; Parquet dependencies and temporary
files are on D:. Validation did not start another paid data-processing run.

The repository audit covers module ownership, seven data resources including
the retained legacy connection, parameterized names and all 17 new-module
variable descriptions. Credential checks found no matching secrets or
credential files in submission candidates or scanned Git history. These
are pattern-based checks rather than an exhaustive guarantee.

## Submission sequence

Commit the validated files and verification output before creating and pushing
`lab2-submit`. Canvas receives the repository URL. The tag selects the grading
commit and must remain fixed. Console screenshots are not required for Lab 2.

After Canvas submission, review and approve exact teardown targets, run the
updated script, then commit `docs/lab2-destroy-output.txt` on `main` and push.
Every final check must be `OK`, with no `CHECK FAILED` or `STILL PRESENT`.
Missing valid teardown evidence caps Task 1 at half its points.

No Canvas submission or resource teardown is included in this preparation.
The NAT and other deployed resources still exist; their idle billing ends
only after the relevant resources are removed.

# Lab 2 — Final Validation

Verification completed on 2026-10-03 America/Denver (2026-10-04 UTC), against
AWS account `173506956686` in `us-east-1` and the current local working tree.

## Results

| Check | Result | Evidence |
|-------|--------|----------|
| Course resource, data-quality and deliverable verifier | 47 passed, 0 failed; exit code 0 | [Complete output](lab2-verify-output.txt) |
| Full processed, feature and offline-store audit | 74 passed, 0 failed; downloaded-file hashes rechecked during final validation | [Explanation](lab2-parquet-audit.md), [assertions and hashes](lab2-parquet-audit.json) |
| Recursive Terraform formatting | Exit code 0; no formatting differences | `terraform fmt -check -recursive infrastructure` |
| Dev configuration validation | `valid: true`, 0 errors, 0 warnings | `terraform -chdir=infrastructure/environments/dev validate -json` |
| Local configuration validation | `valid: true`, 0 errors, 0 warnings | `terraform -chdir=infrastructure/environments/local validate -json` |
| Required Task 1 LocalStack evidence | Existing execution evidence reports PASS: three IAM roles with policies, VPC and public/private subnets, NAT skipped | [LocalStack output](lab2-localstack-output.txt) |
| Local Glue code matches deployed code | SHA-256 matches for both scripts freshly downloaded from S3 | [Script hashes](lab2-deployed-script-hashes.json) |
| Repository structure and credential checks | 14 passed, 0 failed | [Machine-readable report](lab2-repo-quality.json) |
| All-revision course credential scan | Exit code 0; no matches or credential-bearing files found | [Scan output](lab2-secrets-check.txt) |

The course verifier confirmed the private subnet, available NAT Gateway,
SageMaker Domain in `VpcOnly` mode, IAM role boundaries, five S3 lifecycle
rules, catalog table, successful Glue jobs, data-quality assertions, Feature
Group definitions, and an online `GetRecord` response with 16 fields.

The independent full audit covers all 157,627 processed transactions and all
9,999 feature customers. It also verifies that all 9,999 offline records for
the recorded ingestion event match the feature job output. The online store
was sampled; every online record was not independently checked.

## Verifier execution and Windows fix

The repository's `scripts/verify-lab2.sh` now writes its Python tally file with
`open(..., "w", newline="\n")`. Windows otherwise writes CRLF; Git Bash then
reads a trailing carriage return into the failure counter, causing an
arithmetic error. This one-line change fixes summary accounting without
changing any course assertion or expected value. The script passed Bash
syntax checking and the repeated real-AWS verification exited cleanly.

For this execution, a temporary copy outside Git replaced only
`rm -rf "${TMP}"` with a message identifying the retained download directory.
This honors the user's requirement to approve deletion separately. All
verification assertions were retained. The repository script still has its
original temporary cleanup for ordinary use.

The source SHA-256 used for the temporary copy was
`c089b781b995df1e7b6e0156a32075513bf75ca3c45cd9dcc94afd0e52e6a73c`.
The adaptation receipt and downloaded files remain under the course
workspace's `.tools/parquet-validation/` on D:, outside the submission repo.
The last pre-commit run retained its files in `verify-tmp/tmp.foRYQ55Gaq`.
The committed verifier transcript omits trailing alignment spaces only;
all messages and results are unchanged. The raw transcript is retained as
`.tools/parquet-validation/course-verifier-output-precommit.raw.txt`.

The existing Python runtime was reused through a Git Bash `python3` shim;
Parquet dependencies and temporary downloads were located on D:.
AWS operations in this final validation were reads and downloads. No apply,
Glue job start, resource deletion or cloud reconfiguration was performed.

## Repository quality scope

The static audit confirmed that Glue resources belong to `modules/glue/`,
the Feature Group belongs to `modules/feature_store/`, the expected six data
resources are defined, resource names use parameters or resource references,
and all 16 new module variables have descriptions. The literal `glueetl` in
a Glue command block specifies the runtime type; it is not a resource name.

The README describes the modules and ordered pipeline, and the existing apply
evidence contains both successful apply and SageMaker Domain creation.
Working-tree submission candidates and Git history had no matches under the
AWS credential scanners used. Ignore rules protect credentials, state and
local Terraform settings. These are pattern-based checks, not a guarantee
that every possible secret format is detected.

## Remaining handoff

These passing checks establish technical validation of this recorded batch;
they are not a grade or a submission receipt. The following actions remain:

1. Review and commit the intended Lab 2 working-tree changes
2. Push the commit and the required `lab2-submit` tag
3. Submit the repository URL in Canvas
4. Review the exact teardown targets, obtain deletion approval, destroy the
   lab resources after submission, and save the required cleanup evidence

The full guide requires `docs/lab2-destroy-output.txt`. Until valid cleanup
evidence is supplied, Task 1 is capped at half its points. Technical checks
passing does not satisfy that post-submission requirement.

This validation step performed none of those handoff actions. The NAT Gateway
was still available at verification time; its idle billing continues until
the resource is removed. Live resource status and future data batches must
be checked again when needed.

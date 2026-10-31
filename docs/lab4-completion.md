# Lab4 completion and handoff

Implementation, real AWS verification, evidence export and cleanup completed on
2026-10-31. Final training source is `9aff0e5dd81304ab29af530c254c554e7878227a`.
The final documentation commit is later, after deleting CI, as required by the guide.

| Run | Source | CodeBuild suffix | Result | Model |
| --- | --- | --- | --- | --- |
| Initial green | a72d3155 | d151aa6b-6eba-4d41-ba46-bc6d4ca39b76 | SUCCEEDED | v2, operator Approved |
| Intentional failure | 3cd9a16b | 54280ff4-cb20-4013-a80b-9c8787c415ea | PRE_BUILD FAILED | Still v2; no training |
| Revert green | 9aff0e5d | 7376b239-228d-4223-8d94-0cc5d73c83ac | SUCCEEDED, 82 passed, no skips | v3, operator Approved |

Failure and revert were real WebhookV2 push executions. First green was triggered
by CreatePipeline. Final regression actually read Approved v2 AUC 0.7775. Final
candidate AUC 0.7775, precision .7000, recall .3182, lift CI [.0338,.0739].
The fairness gap .3928 remains a nonblocking warning; Platinum has 21 positives.
The received alarm email is preserved as an original screenshot and receipt metadata.

The shared feature module and actual Glue output matched 9,999 customers, all
eleven features and holdout labels. Fresh data tests passed 28; pure feature and
Registry contracts 33; final model/fairness 21. Historical stale-data failure is
kept separately. Both official training adapter files remained byte-identical.

Evidence: full green/failed build logs, both training logs, pipeline histories,
three failure snapshots, alarm email PNG/JSON, Registry/package exports, v2/v3
lineage fields and graph, data manifest, MLflow runs, parity checks and assessment.
`lab4-model-registry.json` records the pre-teardown Approved states. Before S3
deletion, v2/v3 were changed to Rejected for cleanup; `lab4-cleanup.json` records
the final states. This was not a quality failure.

The CI stack, artifact bucket, data bucket and course logs were deleted after
export. Terraform destroyed 40 resources; all independent cleanup checks passed.
NAT lived 30m30s and was removed early. Both Spot jobs totaled 104 billable seconds.
The runtime ledger uses a conservative approximately USD 1 working allowance,
not a final invoice. Cost Explorer is delayed. Existing backend, free connection,
serverless MLflow App and non-running Registry/job records are intentionally retained.

The private offline learning notes use Lab3 palettes and cover foundations,
real implementation, code differences and interactive simulations. Static and
mock DOM checks passed; browser visual QA remains unverified because local-file
navigation was explicitly blocked and was not bypassed.

No grading tag or Canvas submission was performed. After owner review, create
and push `lab4-submit` at the final docs commit, then submit the repository URL
`https://github.com/EasonZhuu/cs401r-easonzhu` in Canvas. Never overwrite an
existing grading tag automatically.

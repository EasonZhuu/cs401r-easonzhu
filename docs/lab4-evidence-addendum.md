# Final model approval timeline and snapshot qualification

The original `AFTER REVERT` snapshot in `lab4-failure-demo.txt` shows v3 as
Approved. The guide's rubric asks for that snapshot to show the newly created
version as PendingManualApproval. The operator approved v3 after the successful
final build but before capturing this snapshot. This timing differs from the
specified capture order. The original evidence has not been rewritten or
backdated; it remains an actual post-approval snapshot.

AWS CloudTrail independently records the successful operations below, exported
in `lab4-v3-approval-audit.json`:

| UTC time, 2026-10-31 | Actual operation | Requested model state |
| --- | --- | --- |
| 21:17:16 | CreateModelPackage, v3 | PendingManualApproval |
| 21:21:26 | UpdateModelPackage, v3 | Approved |
| 21:21:56 | UpdateModelPackage, v3 | Metadata update; no approval change |
| 21:25:56 | UpdateModelPackage, v3 | Rejected for teardown |

The final build completed at 21:17:54 UTC with 82 passing tests and no skips.
It compared the candidate against Approved v2, not against itself. V3 started
PendingManualApproval as designed. Its later approval was an authorized operator
action. The final Rejected status was required lifecycle cleanup before deleting
S3 artifacts, not a failed quality gate.

This audit supplements the evidence but does not manufacture the missing
pre-approval snapshot. The failure demonstration still has the same latest
version v2 before and after the failed PRE_BUILD run, and v3 after revert.
No new training was started to obtain this audit. Exact acceptance of the
snapshot timing deviation remains the grader's decision.

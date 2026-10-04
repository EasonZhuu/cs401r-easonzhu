# Lab 2 — Post-Submission Cleanup

Canvas confirmed **Submitted!**, displaying **Oct 3 at 10:36pm**, for
`https://github.com/EasonZhuu/cs401r-easonzhu`. The grading tag `lab2-submit`
remains fixed at `97280b6b10da839c82dbc86c82ca24e3fd41b49f`.
This cleanup evidence is added to `main` after that tag, as required.

## Actual cleanup and final result

The user explicitly authorized the reviewed deletion targets in AWS account
`173506956686`, region `us-east-1`, for VPC `vpc-0b1abbd3ed5a46984`.
The first Terraform destroy deleted **36 resources**. The reviewed plan had
42 resources: six S3 objects were already absent after the script emptied
**82 object versions**, so Terraform removed them during refresh.

The first final check found three lineage contexts and one DataSet artifact.
A direct delete confirmed an association dependency. Structured AWS CLI calls
then removed the three associations and deleted all four Lab 2 entities.
The complete teardown script was rerun successfully: **exit code 0, all ten
final checks OK**, with no failed or remaining-resource checks in that final
run. Terraform state lists no managed resources.

[The real command output](lab2-destroy-output.txt) includes the first destroy,
the supplemental lineage cleanup, and the final successful script rerun.
It preserves the initial dependency error and the subsequent successful
responses; only terminal ANSI formatting was removed.
[The verification report](lab2-teardown-verification.json) records the final
checks and preservation checks.

## Scope and preservation

The repository's official teardown script is unchanged. An external execution
copy restricted EFS enumeration to `fs-0253d3025800228e6`, and restricted Glue
ENI and SageMaker NFS security-group enumeration to the current Lab 2 VPC.
This avoided deleting two old NFS groups in the account's default VPC.
The source and scoped-copy hashes are recorded in the verification report.

NAT gateways, Elastic IPs, SageMaker domains, Feature Groups, EFS filesystems,
Glue jobs, NorthStar VPCs, lineage contexts, lineage artifacts and Glue
databases all passed the final absence checks. The lab data bucket and its
object versions were deleted, and the four Glue log groups were removed.

The remote Terraform state bucket `northstar-tfstate-173506956686` and the
`northstar-tfstate-lock` DynamoDB table are retained for Lab 3. The lock table
was verified `ACTIVE`. The default VPC's two older NFS groups remain intact.
Local files, data-validation snapshots, Git history and the grading tag were
preserved. Deployed pipeline verification remains available at `lab2-submit`;
cloud resource checks will now find the lab resources absent until redeployed.

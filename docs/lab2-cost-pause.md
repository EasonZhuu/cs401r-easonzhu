# Lab 2 cost pause

The user requested a temporary pause on 2026-10-03 (America/Denver).

Current status: restored at the user's subsequent request. The NAT Gateway, Elastic IP, and private default route have been recreated, so their hourly charges have resumed. See `lab2-cost-resume-output.txt` and `lab2-cost-resume-verification.json` (9/9 checks passed).

## Verified state during the pause (historical)

- AWS account: `173506956686`; region: `us-east-1`
- NAT Gateway `nat-0fcdf9b27a9de1ce5`: `deleted`
- Elastic IP `eipalloc-0885332acfafb1486`: released; `describe-addresses` returned an empty list
- Private subnet default route through that NAT: removed
- No SageMaker apps in domain `d-zidesvgztgmj`, no NorthStar endpoints, and no NorthStar training or processing jobs in progress
- No NorthStar EC2 instances or VPC endpoints
- No Glue ETL jobs; the raw crawler is `READY`, last run `SUCCEEDED`, with no schedule
- Terraform lock table uses `PAY_PER_REQUEST`
- S3 data, Glue metadata, SageMaker domain, and its EFS storage remain
- EFS size at verification: 6144 bytes; throughput mode: `bursting`
- Retained storage and requests may still incur charges; this is not a zero-cost teardown
- Final Terraform plan: `No changes`

## Resume

During the pause, the ignored local file `infrastructure/environments/dev/cost-pause.auto.tfvars` set `enable_nat_gateway = false`. Following the user's request to resume, its current value is `true` and the restoration has been applied.

To resume, set it to `true`, review a fresh Terraform plan, and apply it. This recreates the NAT Gateway, Elastic IP, and private subnet default route and resumes their hourly charges. Private subnet internet access is unavailable while the pause remains active.

Restored resource IDs: NAT `nat-0e659a71352bfd549`; Elastic IP allocation `eipalloc-076c9c227646368ea`. The private default route is active and points to the restored NAT. SageMaker remains `InService`, `VpcOnly`, and assigned to the original private subnet.

The module and dev variable defaults remain `true` for the required lab architecture; the pause override is local and is not committed. Restoring the infrastructure is necessary before the final lab verification.

The first apply was interrupted after requesting NAT deletion and left a state lock. After confirming no Terraform process remained, that apply's lock was released and a fresh plan applied only the remaining Elastic IP deletion. Both apply logs are retained in this directory.

# Lab 1 Cost Estimate and Optimization Plan

This is a short-lived development/lab deployment in `us-east-1`. Exact prices
depend on region, usage, and AWS pricing changes; the figures below are
planning estimates, not an invoice. The safest cost strategy is to keep the
resources small, avoid data transfer, and destroy the stack after evidence is
captured.

| Component | Monthly Estimate | Key Assumptions | One Optimization |
|---|---|---|---|
| SageMaker Studio | **$18.00/month** | One small app for 2 hours/day × 30 days × an assumed $0.30/hour; stopped apps incur no compute charge | Stop the app after each session: avoiding 22 idle hours/day saves about **$198/month** at the same rate |
| S3 storage | **$0.01/month** | 0.1 GB of sample data at about $0.023/GB-month; four prefixes and requests are negligible | Expire temporary artifacts and keep only sample data |
| Internet Gateway | **$0.01/month** | No hourly gateway fee; assume only about 1 GB of lab transfer at a small planning allowance | Avoid downloads/uploads and do not add a NAT Gateway for Lab 1 |
| DynamoDB (state lock) | **$0.01/month** | PAY_PER_REQUEST with near-zero reads/writes and one small lock item | Delete the lock table after the remote state is no longer needed |
| S3 state bucket | **$0.01/month** | One small versioned state object and negligible requests | Keep versioning during the lab, then empty/delete it after the final submission |
| **Total** | **$18.04/month** | Five components above; VPC, subnet, routes, and security group have no separate hourly charge | Destroy the development stack after evidence capture |

## Optimization target

For a two-hour lab session, the target is to keep direct service usage below
roughly **$0.60**, with the SageMaker compute instance being the dominant
component. The highest-value action is stopping the Studio app immediately
after use; leaving a small app running overnight costs more than all of the
metadata resources combined. The second action is deleting the data bucket,
state bucket, and lock table after the final screenshots and verification
output are committed. No NAT gateway, managed database, or multi-AZ transfer
is justified by this milestone.

## Assumptions and exclusions

This estimate excludes any existing account-wide free-tier credits, support
plans, taxes, unrelated resources, and future Lab 2 services. It also assumes
that the S3 bucket remains nearly empty and that the SageMaker domain has only
one small user profile. Before submission, AWS Cost Explorer should be used to
confirm that no unexpected resource remains in `us-east-1`.

# Lab 2 - Dev Terraform Plan Review

Reviewed on 2026-10-02 (America/Denver), using the real AWS account and remote state.
This review did not run `terraform apply`.

Deployment was subsequently completed on 2026-10-02 (America/Denver).
See [the actual apply log](lab2-extend-output.txt) and
[the live Task 1 verification report](lab2-task1-aws-verification.json).
The MLEngineer trust policy was given conditional source-account/source-ARN
checks before a fresh plan was generated. That plan still had 32 creates and no
updates or deletes. Apply succeeded, all 37 live checks passed, and the
post-apply plan reported no changes.

## Target

- AWS account: `173506956686`
- Region: `us-east-1`
- Environment: `dev`
- State bucket: `northstar-tfstate-173506956686`
- State key: `dev/terraform.tfstate`
- State locking table: `northstar-tfstate-lock`

## Plan result

```text
Plan: 32 to add, 0 to change, 0 to destroy.
```

| Module | Resources to create | Purpose |
|---|---:|---|
| vpc | 12 | VPC, public/private subnets, Internet Gateway, public NAT with an EIP, route tables/routes/associations, and SageMaker security group |
| storage | 9 | Data bucket, public-access block, versioning, encryption, four prefix objects, and one lifecycle configuration containing five rules |
| iam | 9 | MLEngineer, DataEngineer, and ModelMonitor: one role, policy, and attachment each |
| sagemaker | 2 | Studio Domain and MLEngineer user profile |
| Total | 32 | All actions are create; no resource deletion or replacement |

The refreshed prior state contained no managed platform resources. Read-only AWS
queries also found no project roles, no `northstar-dev-domain`, no VPC named
`northstar-dev-vpc`, and no `northstar-dev-data-173506956686` bucket. The SageMaker
service-linked role `AWSServiceRoleForAmazonSageMakerNotebooks` already exists.

## Configuration checks

- SageMaker receives `module.vpc.private_subnet_id`; Domain network access is `VpcOnly`
- Private subnet CIDR is `10.0.1.0/24`, with automatic public IP assignment disabled
- Public subnet CIDR is `10.0.100.0/24`
- Public NAT is placed in the public subnet and uses the planned EIP
- Private default route points to that NAT
- Lifecycle configuration includes exactly these five enabled rules:

| Rule | Prefix | Expiration |
|---|---|---|
| expire-raw-data | raw/ | Current version after 90 days |
| expire-raw-versions | raw/ | Noncurrent versions after 30 days |
| expire-processed-versions | processed/ | Noncurrent versions after 30 days |
| expire-feature-versions | features/ | Noncurrent versions after 60 days |
| expire-datacapture | datacapture/ | Current version after 7 days |

## Interpretation and limits

The live plan calls for a new SageMaker Domain. The guide's Domain replacement
case applies when an existing Domain is still managed; it does not occur here.

Zero destroys describes this infrastructure change. After deployment, lifecycle
rules still expire data according to the configured retention periods.

A successful plan does not verify successful resource creation, service quotas,
runtime permissions, network connectivity, or the Domain reaching `InService`.
Those checks follow the actual apply. The current plan contains no Glue jobs,
crawler, or Feature Group; those belong to the later data-pipeline tasks.

Creating the NAT and public IPv4 address introduces running charges. See
[AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

The binary plan and raw diagnostic output are retained outside the repository
under `.tools/dev-validation/`. Regenerate the plan before deployment if the
configuration or cloud resources change.

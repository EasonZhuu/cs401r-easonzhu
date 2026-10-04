# infrastructure/ — NorthStar Lab 2 Terraform

This directory contains the implemented Lab 1 platform and Lab 2 extensions.
For prerequisites, AWS deployment, pipeline execution, validation evidence and
submission instructions, see the [repository README](../README.md).

## Module ownership

| Module | Owned resources |
|--------|-----------------|
| `modules/vpc/` | VPC, subnets, Internet Gateway, NAT Gateway/EIP, route tables/associations, SageMaker and Glue security groups |
| `modules/storage/` | Data bucket, public-access block, versioning, encryption, lifecycle rules and initial prefix markers |
| `modules/iam/` | MLEngineer, DataEngineer and ModelMonitor IAM roles, policies and attachments |
| `modules/sagemaker/` | SageMaker Domain and user profile |
| `modules/glue/` | Catalog database, crawler, NETWORK connection, both job-script S3 objects and both Glue jobs |
| `modules/feature_store/` | SageMaker customer Feature Group and its online/offline configuration |

`environments/dev/main.tf` connects these modules through inputs and outputs.
For example, VPC provides the private subnet and Glue security group, IAM
provides the DataEngineer role, and storage provides the data bucket. Glue owns
the Catalog database; Feature Store's offline configuration uses that database
and asks SageMaker to create its managed table there.

## Environments

- **dev:** real AWS in `us-east-1` by default; all six modules; SageMaker and Glue
  compute use the private subnet and require NAT for outbound access
- **local:** LocalStack VPC/storage/IAM checks; excludes SageMaker and Glue,
  disables NAT and S3 lifecycle rules; see the [local guide](environments/local/README.md)

The dev remote backend uses a separate S3 state bucket and DynamoDB lock table.
Bootstrap them before the first `terraform init`. A new AWS account must use
its own backend bucket; the root README shows the account-derived override.

## Naming and validation

Resource names are built from `var.project` and `var.environment`; the storage
bucket additionally includes the authenticated account ID. Pass names and ARNs
between modules instead of repeating resource definitions. Feature names,
Catalog table names and S3 prefix conventions describe the data schema/layout.

From the repository root, after initializing the relevant environments:

```bash
terraform fmt -check -recursive infrastructure
terraform -chdir=infrastructure/environments/dev validate
terraform -chdir=infrastructure/environments/local validate
```

Formatting and configuration validation do not deploy resources or execute
the data pipeline. Use a reviewed plan and apply for real AWS changes, then run
the crawler, transform and feature job in the order documented in the root README.

## ADR-001: NorthStar Platform Foundation

### Status

Accepted

**Date:** 2026-09-19

### Context

Lab 1 needs a small, repeatable AWS foundation for the NorthStar retail ML
workload. It is the shared base for the three-system platform: churn scoring,
LLM serving, and the data/feature pipeline. The foundation must support a
SageMaker Studio user, durable data storage, a public single-AZ network, and
infrastructure that can be recreated from source control. The lab is
intentionally a development foundation rather than a production landing zone,
so the design should remain simple enough to validate and destroy during the
exercise while still demonstrating least privilege and state locking.

### Decision

We use Terraform modules for four concerns: VPC networking, IAM, storage, and
SageMaker. The dev environment composes those modules and stores Terraform
state in an S3 backend protected by a DynamoDB lock table.

The network is one VPC with CIDR `10.0.0.0/16`, one public subnet with CIDR
`10.0.100.0/24`, an internet gateway, and a route table containing the local
route plus `0.0.0.0/0` to the internet gateway. A dedicated security group is
used by SageMaker. This single-public-subnet layout matches the Lab 1 scope;
private subnets and NAT are deferred until a later lab. It gives the churn
scoring notebooks and the future LLM-serving experiments a predictable
development path without pretending that this public topology is production
isolation.

The data layer uses one S3 bucket named from the project and account context.
The bucket has versioning, default SSE-S3 encryption, and all-public-access
blocking enabled. Four prefixes organize the lifecycle of the data:
`raw/`, `processed/`, `features/`, and `artifacts/`. The same bucket is also
used by the SageMaker execution role for the lab's permitted data operations.

The execution role is `northstar-dev-MLEngineer`. Its trust policy allows only
the SageMaker service to assume it. The attached AWS-managed
`AmazonSageMakerFullAccess` policy supplies the lab's baseline Studio access,
while the customer-managed policy grants the NorthStar-specific S3 and
CloudWatch actions. The IAM simulation in the verification script confirms
that the role can create a SageMaker training job but is denied writing to
`raw/`, leaving ingestion ownership for the later Data Engineer role.

SageMaker is configured with IAM authentication, public internet access, the
single public subnet, the dedicated security group, and one `MLEngineer` user
profile. This is enough for the ML engineer to prepare churn features and test
LLM-serving code against the shared artifact/feature paths. The domain and
user profile are created by Terraform so the same configuration can be
reviewed, applied, and destroyed consistently.

### Consequences

#### What this makes easy

This design is easy to understand, inexpensive for a short-lived lab, and
reproducible from the repository. S3 encryption/versioning and public-access
blocking provide useful baseline safeguards. Remote state plus a DynamoDB lock
prevents two Terraform processes from writing state at the same time.

#### What this makes harder

The trade-off is that the network is not production-grade: it has one
availability zone, public internet access, no private subnets, and no NAT
gateway. The AWS-managed full-access policy is broader than an ideal
production policy. The domain and S3 resources can also incur charges if they
are left running, so the lab requires an explicit shutdown and destroy step.

#### What would cause us to revisit this decision

We would revisit this layout when churn scoring needs private data access, when
LLM serving requires a production endpoint, or when more than one Availability
Zone is required for availability. A second VPC tier, private subnets, NAT or
VPC endpoints, a customer-managed KMS key, and narrower service roles would
then be justified. A growing team would also require separate Data Engineer
and Model Monitor roles instead of expanding the MLEngineer policy.

### Implementation and Operations

The environment module is intentionally the only place that chooses concrete
development values such as the project name, CIDRs, Availability Zone, and
Studio instance type. The child modules consume variables and expose outputs,
which keeps the module contracts reusable for another environment or for Lab 2.
The S3 bucket name includes the AWS account ID because bucket names are global;
the account-derived suffix avoids collisions without hard-coding a personal
identifier in a module. Empty objects with trailing slashes make the four
logical prefixes visible in the console while still allowing the application
to add real objects later.

The role policy is deliberately split into statements so the verification
script can demonstrate both useful access and a denied action. MLEngineer may
read and update model artifacts and features, but it cannot write to `raw/`.
That boundary documents where a future Data Engineer role will own ingestion.
The SageMaker trust policy is service-specific, and the remote state backend
uses DynamoDB locking so two operators cannot update the same state file at
the same time. Before every apply, the operator should run formatting and
validation; after evidence capture, Studio apps should be stopped and the
development stack should be destroyed. The remote state bucket and lock table
are retained because later labs build on the same Terraform state foundation.

### Alternative Considered

We considered a production-style two-AZ VPC with private subnets, NAT
gateways, VPC endpoints, a customer-managed KMS key, and narrowly scoped
service roles. That option would improve isolation and resilience, but it adds
several billable components and operational decisions that are outside Lab 1.
We also considered creating resources manually in the console; that would be
quick for a demo but would not satisfy the module/reproducibility goal or
provide a reliable destroy path. Terraform with a deliberately small public
topology is the better fit for this milestone.

### AWS Service Selection

- **Amazon VPC:** isolated address space, subnet, routing, internet gateway,
  and security-group boundaries.
- **Amazon S3:** durable, encrypted object storage for the four lab data
  stages and Terraform's remote state.
- **AWS IAM:** service trust, execution-role permissions, and the lab's
  least-privilege demonstration.
- **Amazon SageMaker Studio:** managed ML development domain and user profile.
- **Amazon DynamoDB:** on-demand Terraform state-lock table with `LockID` as
  the hash key.

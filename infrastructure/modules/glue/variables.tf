variable "project" {
  description = "Project name used in resource names"
  type        = string
}

variable "environment" {
  description = "Environment name used in resource names"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket containing the raw customer transactions"
  type        = string
}

variable "data_engineer_role_arn" {
  description = "IAM role assumed by the Glue crawler and pipeline jobs"
  type        = string
}

variable "private_subnet_id" {
  description = "Private subnet in which Glue Spark workers run"
  type        = string
}

variable "glue_security_group_id" {
  description = "Shared SageMaker security group with all-protocol self ingress for Glue"
  type        = string
}

variable "legacy_glue_security_group_id" {
  description = "Earlier Glue group retained with its unused connection until approved teardown"
  type        = string
}

variable "availability_zone" {
  description = "Availability Zone of the private subnet"
  type        = string
}

variable "transform_script_path" {
  description = "Local path to the transform script uploaded by Terraform"
  type        = string
}

variable "feature_engineer_script_path" {
  description = "Local path to the feature engineering script uploaded by Terraform"
  type        = string
}

variable "feature_group_name" {
  description = "Customer Feature Group receiving the engineered records"
  type        = string
}

variable "aws_region" {
  description = "AWS region of the Feature Store runtime endpoint"
  type        = string
}

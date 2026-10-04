variable "project" {
  description = "Project name used in resource names"
  type        = string
}

variable "environment" {
  description = "Environment name used in resource names"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket containing the Feature Store offline data"
  type        = string
}

variable "glue_database_name" {
  description = "Existing Glue database permitted by the offline writer role"
  type        = string
}

variable "data_engineer_role_arn" {
  description = "IAM role assumed by SageMaker to write offline feature records"
  type        = string
}

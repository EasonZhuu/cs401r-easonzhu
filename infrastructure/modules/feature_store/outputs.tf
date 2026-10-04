output "feature_group_name" {
  description = "Name of the customer Feature Group"
  value       = aws_sagemaker_feature_group.customers.feature_group_name
}

output "feature_group_arn" {
  description = "ARN of the customer Feature Group"
  value       = aws_sagemaker_feature_group.customers.arn
}

output "offline_store_s3_uri" {
  description = "Configured S3 prefix for offline Feature Store records"
  value       = aws_sagemaker_feature_group.customers.offline_store_config[0].s3_storage_config[0].s3_uri
}

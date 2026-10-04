output "database_name" {
  description = "Name of the Glue Catalog database"
  value       = aws_glue_catalog_database.this.name
}

output "raw_crawler_name" {
  description = "Name of the crawler for raw customer transactions"
  value       = aws_glue_crawler.raw.name
}

output "private_connection_name" {
  description = "Name of the Glue connection to the private subnet"
  value       = aws_glue_connection.vpc_network.name
}

output "transform_job_name" {
  description = "Name of the Glue customer transaction transform job"
  value       = aws_glue_job.transform.name
}

output "feature_engineer_job_name" {
  description = "Name of the customer feature engineering Glue job"
  value       = aws_glue_job.feature_engineer.name
}

locals {
  name_prefix   = "${var.project}-${var.environment}"
  database_name = replace(local.name_prefix, "-", "_")
}

# Store table schemas and S3 locations; data files remain in S3
resource "aws_glue_catalog_database" "this" {
  name        = local.database_name
  description = "NorthStar data catalog: table schemas and S3 locations"
}

resource "aws_glue_crawler" "raw" {
  name          = "${local.name_prefix}-raw-crawler"
  database_name = aws_glue_catalog_database.this.name
  # Glue assumes this role to read raw data and write catalog metadata
  role        = var.data_engineer_role_arn
  description = "Discover the raw customer transaction CSV schema"

  # The customers prefix determines the default catalog table name
  s3_target {
    path = "s3://${var.bucket_name}/raw/customers/"
  }

  # Scan all files on each manual run, including replaced CSV files
  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  # Update detected schemas; log missing data without deleting catalog tables
  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }
}

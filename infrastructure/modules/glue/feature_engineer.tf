resource "aws_s3_object" "feature_engineer_script" {
  bucket       = var.bucket_name
  key          = "artifacts/glue/feature_engineer.py"
  source       = var.feature_engineer_script_path
  source_hash  = filemd5(var.feature_engineer_script_path)
  content_type = "text/x-python"
}

resource "aws_glue_job" "feature_engineer" {
  name              = "${local.name_prefix}-feature-engineer"
  description       = "Aggregate customer features and ingest labelled records into Feature Store"
  role_arn          = var.data_engineer_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  max_retries       = 0
  connections       = [aws_glue_connection.private_network.name]

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/${aws_s3_object.feature_engineer_script.key}"
  }

  default_arguments = {
    "--job-language"        = "python"
    "--job-bookmark-option" = "job-bookmark-disable"
    "--input_path"          = "s3://${var.bucket_name}/processed/customers/"
    "--output_path"         = "s3://${var.bucket_name}/features/customers/"
    "--feature_group_name"  = var.feature_group_name
    "--region"              = var.aws_region
    "--TempDir"             = "s3://${var.bucket_name}/features/_glue_temp/"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}

resource "aws_glue_connection" "vpc_network" {
  name            = "${local.name_prefix}-vpc-connection"
  description     = "Run Glue workers in the NorthStar private subnet"
  connection_type = "NETWORK"

  physical_connection_requirements {
    availability_zone      = var.availability_zone
    subnet_id              = var.private_subnet_id
    security_group_id_list = [var.glue_security_group_id]
  }
}

# Preserve the previously deployed connection until approved lab teardown
# The moved block changes its state address without deleting the AWS object
moved {
  from = aws_glue_connection.private_network
  to   = aws_glue_connection.legacy_private_network
}

resource "aws_glue_connection" "legacy_private_network" {
  name            = "${local.name_prefix}-private-network"
  description     = "Run Glue workers in the NorthStar private subnet"
  connection_type = "NETWORK"

  physical_connection_requirements {
    availability_zone      = var.availability_zone
    subnet_id              = var.private_subnet_id
    security_group_id_list = [var.legacy_glue_security_group_id]
  }
}

resource "aws_s3_object" "transform_script" {
  bucket       = var.bucket_name
  key          = "artifacts/glue/transform.py"
  source       = var.transform_script_path
  source_hash  = filemd5(var.transform_script_path)
  content_type = "text/x-python"
}

resource "aws_glue_job" "transform" {
  name              = "${local.name_prefix}-transform"
  description       = "Clean raw customer transactions and write processed Parquet"
  role_arn          = var.data_engineer_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 10
  max_retries       = 0
  connections       = [aws_glue_connection.vpc_network.name]

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.bucket_name}/${aws_s3_object.transform_script.key}"
  }

  default_arguments = {
    "--job-language"        = "python"
    "--job-bookmark-option" = "job-bookmark-disable"
    "--database_name"       = aws_glue_catalog_database.this.name
    "--table_name"          = "customers"
    "--output_path"         = "s3://${var.bucket_name}/processed/customers/"
    "--TempDir"             = "s3://${var.bucket_name}/processed/_glue_temp/"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}

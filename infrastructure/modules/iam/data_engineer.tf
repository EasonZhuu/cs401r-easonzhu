# DataEngineer permissions for the Lab 2 data pipeline

data "aws_region" "current" {}

resource "aws_iam_role" "data_engineer" {
  name = "${local.name_prefix}-DataEngineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "glue.amazonaws.com",
            "lambda.amazonaws.com",
            "sagemaker.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
        # Some service AssumeRole calls omit source metadata
        # Check the account and source ARN when the service supplies them
        Condition = {
          StringEqualsIfExists = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLikeIfExists = {
            "aws:SourceArn" = [
              "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:crawler/${local.name_prefix}-raw-crawler",
              "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:job/${local.name_prefix}-transform",
              "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:job/${local.name_prefix}-feature-engineer",
              "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function/${local.name_prefix}-*",
              "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
            ]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "data_engineer" {
  name        = "${local.name_prefix}-DataEngineerPolicy"
  description = "Scoped permissions for the NorthStar data pipeline"

  policy = templatefile("${path.module}/policies/data_engineer.json.tftpl", {
    account_id             = data.aws_caller_identity.current.account_id
    region                 = data.aws_region.current.name
    name_prefix            = local.name_prefix
    database_name          = replace(local.name_prefix, "-", "_")
    bucket_arn             = local.bucket_arn
    data_engineer_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name_prefix}-DataEngineer"
  })
}

resource "aws_iam_role_policy_attachment" "data_engineer" {
  role       = aws_iam_role.data_engineer.name
  policy_arn = aws_iam_policy.data_engineer.arn
}

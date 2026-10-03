# Observer permissions for model monitoring
resource "aws_iam_role" "model_monitor" {
  name = "${local.name_prefix}-ModelMonitor"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      # Check source metadata when SageMaker supplies it
      Condition = {
        StringEqualsIfExists = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnLikeIfExists = {
          "aws:SourceArn" = "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "model_monitor" {
  name        = "${local.name_prefix}-ModelMonitorPolicy"
  description = "Read model artifacts and processing jobs, and publish monitoring telemetry"

  policy = templatefile("${path.module}/policies/model_monitor.json.tftpl", {
    account_id  = data.aws_caller_identity.current.account_id
    region      = data.aws_region.current.name
    name_prefix = local.name_prefix
    bucket_arn  = local.bucket_arn
  })
}

resource "aws_iam_role_policy_attachment" "model_monitor" {
  role       = aws_iam_role.model_monitor.name
  policy_arn = aws_iam_policy.model_monitor.arn
}

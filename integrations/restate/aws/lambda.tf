# ── Restate handler deployed as AWS Lambda ──
#
# Restate server (EC2) invokes this Lambda for each request.
# State is managed by Restate's embedded KV via the SDK.

data "archive_file" "handler_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_package"
  output_path = "${path.module}/restate_handler_bundle.zip"
}

resource "aws_lambda_function" "handler" {
  function_name = "${local.name_prefix}-handler"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.app"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  filename         = data.archive_file.handler_zip.output_path
  source_code_hash = data.archive_file.handler_zip.output_base64sha256

  # No VPC — Restate server calls Lambda via AWS invoke API
  # State managed by Restate server, not Lambda

  tags = {
    Name = "${local.name_prefix}-handler"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
  ]
}

# Publish a version — Restate requires registering a specific version, not $LATEST
resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Restate deployment target"
  function_name    = aws_lambda_function.handler.function_name
  function_version = aws_lambda_function.handler.version
}

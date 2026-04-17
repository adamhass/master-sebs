# ── Lambda Durable Function + DynamoDB State ──
#
# Extends the baseline stack with a durable execution Lambda that uses
# DynamoDB for state storage instead of Redis.  No VPC needed.

# --- DynamoDB table for durable function state ---

resource "aws_dynamodb_table" "durable_state" {
  name         = "${local.name_prefix}-durable-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "state_key"

  attribute {
    name = "state_key"
    type = "S"
  }

  tags = {
    Name = "${local.name_prefix}-durable-state"
  }
}

# --- Lambda function (durable execution) ---

data "archive_file" "durable_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_durable_package"
  output_path = "${path.module}/lambda_durable_bundle.zip"
}

resource "aws_lambda_function" "durable" {
  function_name = "${local.name_prefix}-durable-fn"
  role          = aws_iam_role.lambda_durable.arn
  handler       = "handler.handler"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  filename         = data.archive_file.durable_zip.output_path
  source_code_hash = data.archive_file.durable_zip.output_base64sha256

  # Enable durable execution (checkpoint/replay)
  durable_config {
    execution_timeout = 300
    retention_period  = 1
  }

  # No VPC — DynamoDB accessed via public AWS endpoint
  # No Redis dependency

  environment {
    variables = {
      DDB_TABLE = aws_dynamodb_table.durable_state.name
    }
  }

  reserved_concurrent_executions = var.lambda_reserved_concurrent_executions >= 0 ? var.lambda_reserved_concurrent_executions : null

  depends_on = [
    aws_iam_role_policy_attachment.durable_basic,
    aws_iam_role_policy_attachment.durable_execution,
    aws_iam_role_policy.durable_dynamodb,
  ]

  publish = true

  tags = {
    Name = "${local.name_prefix}-durable-fn"
  }
}

resource "aws_lambda_alias" "durable_live" {
  name             = "live"
  description      = "Durable function live alias"
  function_name    = aws_lambda_function.durable.function_name
  function_version = aws_lambda_function.durable.version
}

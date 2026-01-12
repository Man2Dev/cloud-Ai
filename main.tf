##########################
# Data Sources
##########################
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

##########################
# CloudWatch Log Group
##########################
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Purpose = "Lambda function logs"
  })
}

##########################
# S3: chatbot-conversations
##########################
resource "aws_s3_bucket" "chatbot_conversations" {
  bucket = "${local.s3_bucket_prefix}-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.common_tags, {
    Purpose = "Store archived user conversation transcripts"
  })
}

resource "aws_s3_bucket_versioning" "chatbot_conversations" {
  bucket = aws_s3_bucket.chatbot_conversations.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "chatbot_conversations" {
  bucket = aws_s3_bucket.chatbot_conversations.id

  rule {
    id     = "archive-old-conversations"
    status = "Enabled"

    filter {
      prefix = "archives/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

##########################
# DynamoDB: chatbot-sessions
##########################
resource "aws_dynamodb_table" "chatbot_sessions" {
  name         = local.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "N"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "model_name"
    type = "S"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "is_active"
    type = "N"
  }

  attribute {
    name = "last_message_ts"
    type = "N"
  }

  global_secondary_index {
    name            = "model_index"
    hash_key        = "model_name"
    range_key       = "session_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "active_sessions_index"
    hash_key        = "is_active"
    range_key       = "last_message_ts"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(local.common_tags, {
    Purpose = "Store user sessions and conversation data"
  })
}

##########################
# Lambda packaging
##########################
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/package"
  output_path = "${path.module}/lambda_function.zip"
  excludes    = []
}

##########################
# Lambda Function
##########################
resource "aws_lambda_function" "telegram_bot" {
  function_name    = local.lambda_function_name
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = local.lambda_handler
  runtime          = local.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  # Use the pre-existing LabRole from AWS Academy
  role = var.lab_role_arn

  environment {
    variables = {
      TELEGRAM_TOKEN = var.telegram_token
      S3_BUCKET_NAME = aws_s3_bucket.chatbot_conversations.bucket
      ENVIRONMENT    = var.environment
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_s3_bucket.chatbot_conversations,
    aws_dynamodb_table.chatbot_sessions
  ]

  tags = merge(local.common_tags, {
    Purpose = "Telegram bot message handler"
  })
}

##########################
# API Gateway (REST API)
##########################
resource "aws_api_gateway_rest_api" "telegram_api" {
  name        = local.api_gateway_name
  description = "API Gateway for Telegram Bot webhook"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.telegram_api.id
  parent_id   = aws_api_gateway_rest_api.telegram_api.root_resource_id
  path_part   = "webhook"
}

resource "aws_api_gateway_method" "webhook_post" {
  rest_api_id   = aws_api_gateway_rest_api.telegram_api.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.telegram_api.id
  resource_id             = aws_api_gateway_resource.webhook.id
  http_method             = aws_api_gateway_method.webhook_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.telegram_bot.invoke_arn
}

resource "aws_api_gateway_deployment" "telegram_deployment" {
  depends_on = [
    aws_api_gateway_integration.lambda_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.telegram_api.id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.telegram_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.telegram_api.id
  stage_name    = var.environment == "prod" ? "prod" : "dev"

  tags = local.common_tags
}

##########################
# Lambda Permission for API Gateway
##########################
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_bot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.telegram_api.execution_arn}/*/*"
}

##########################
# Variables
##########################
variable "telegram_token" {
  description = "Telegram bot token passed as environment variable to Lambda"
  type        = string
  default     = ""
  sensitive   = true
}

variable "lab_role_arn" {
  description = "ARN of the pre-existing LabRole in AWS Academy"
  type        = string
  default     = ""
}

##########################
# Data Source: Get AWS Account ID
##########################
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

##########################
# S3: chatbot-conversations
##########################
resource "aws_s3_bucket" "chatbot_conversations" {
  bucket = "chatbot-conversations-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store archived user conversation transcripts"
    Env     = "aws-academy"
  }
}

##########################
# DynamoDB: chatbot-sessions
##########################
resource "aws_dynamodb_table" "chatbot_sessions" {
  name         = "chatbot-sessions"
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

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store user sessions and conversation data"
    Env     = "aws-academy"
  }
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
# Lambda Function (using LabRole)
##########################
resource "aws_lambda_function" "telegram_bot" {
  function_name    = "telegram-bot"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.9"
  timeout          = 30
  memory_size      = 256
  
  # Use the pre-existing LabRole from AWS Academy
  role = var.lab_role_arn

  environment {
    variables = {
      TELEGRAM_TOKEN = var.telegram_token
      S3_BUCKET_NAME = aws_s3_bucket.chatbot_conversations.bucket
    }
  }

  depends_on = [
    aws_s3_bucket.chatbot_conversations,
    aws_dynamodb_table.chatbot_sessions
  ]
}

##########################
# API Gateway (REST API)
##########################
resource "aws_api_gateway_rest_api" "telegram_api" {
  name        = "telegram-bot-api"
  description = "API Gateway for Telegram Bot webhook"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Project = "AI-Chatbot"
    Env     = "aws-academy"
  }
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
  stage_name    = "prod"

  tags = {
    Project = "AI-Chatbot"
    Env     = "aws-academy"
  }
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

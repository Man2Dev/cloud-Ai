##########################
# S3: chatbot-conversations
##########################
resource "aws_s3_bucket" "chatbot_conversations" {
  bucket = "chatbot-conversations"

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store archived user conversation transcripts"
    Env     = "local"
  }
}

##########################
# S3: chatbot-user-files
##########################
resource "aws_s3_bucket" "chatbot_user_files" {
  bucket = "chatbot-user-files"

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store user-uploaded files"
    Env     = "local"
  }
}


##########################
# DynamoDB: chatbot-sessions
##########################
resource "aws_dynamodb_table" "chatbot_sessions" {
  name         = "chatbot-sessions"
  billing_mode = "PAY_PER_REQUEST"

  # Primary key schema: pk (user partition) + sk (model+session sort)
  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "N"  # Telegram user ID
  }

  attribute {
    name = "sk"
    type = "S"  # Composite: SESSION#<id>, PROFILE, or MESSAGE#<id>
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

  # GSI for querying by model across all users
  global_secondary_index {
    name            = "model_index"
    hash_key        = "model_name"
    range_key       = "session_id"
    projection_type = "ALL"
  }

  # GSI for querying active sessions across all users
  global_secondary_index {
    name            = "active_sessions_index"
    hash_key        = "is_active"
    range_key       = "last_message_ts"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store user sessions and conversation data"
    Env     = "local"
  }
}
# -----------------------
# Lambda packaging + function
# -----------------------

variable "telegram_token" {
  description = "Telegram bot token passed as environment variable to Lambda"
  type        = string
  default     = ""  # Set via CLI or tfvars for testing
  sensitive   = true
}

# Use pre-built zip (from build_lambda.sh) instead of source_file
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/package"  # Assumes build_lambda.sh ran
  output_path = "${path.module}/lambda_function.zip"
  excludes    = []  # Zip everything in package/
}

resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "lambda_policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:*",
          "s3:*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "telegram_bot" {
  function_name    = "telegram-bot"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  handler          = "handler.lambda_handler"  # Expects handler.py in zip root
  runtime          = "python3.9"
  role             = aws_iam_role.lambda_exec.arn

  environment {
  variables = {
    TELEGRAM_TOKEN     = var.telegram_token
    USER_FILES_BUCKET  = aws_s3_bucket.chatbot_user_files.bucket
  }
}
}

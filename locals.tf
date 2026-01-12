##########################
# Local Values
##########################

locals {
  # Project identification
  project_name = "ai-chatbot"

  # Naming convention: {project}-{resource}-{environment}
  name_prefix = "${local.project_name}-${var.environment}"

  # Common tags applied to all resources
  common_tags = {
    Project     = "AI-Chatbot"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Repository  = "github.com/Man2Dev/cloud-Ai"
  }

  # Resource-specific names
  lambda_function_name = "telegram-bot"
  dynamodb_table_name  = "chatbot-sessions"
  s3_bucket_prefix     = "chatbot-conversations"
  api_gateway_name     = "telegram-bot-api"

  # Lambda configuration
  lambda_runtime = "python3.9"
  lambda_handler = "handler.lambda_handler"
}
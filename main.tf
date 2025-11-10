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
    type = "N"  # Number (Telegram user ID)
  }

  attribute {
    name = "sk"
    type = "S"  # String (UUID or timestamp-based)
  }

  # Attribute used by GSI
  attribute {
    name = "model_name"
    type = "S"  # i.e., "gpt-4", "gpt-3.5-turbo"
  }

  attribute {
    name = "session_id"
    type = "S"  # String (UUID or timestamp-based)
  }

  attribute {
    name = "is_active"
    type = "N"  # Number: 1 = active, 0 = archived
  }

  attribute {
    name = "last_message_ts"
    type = "N"  # Number (timestamp)
  }

  # GSI 1: Query by model across all users
  global_secondary_index {
    name            = "model_index"
    hash_key        = "model_name"
    range_key       = "session_id"
    projection_type = "ALL"
  }

  # GSI 2: Query active sessions across all users
  global_secondary_index {
    name            = "active_sessions_index"
    hash_key        = "is_active"
    range_key       = "last_message_ts"
    projection_type = "ALL"
  }

  # TTL: Automatically delete old archived sessions
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Track user sessions, model selection, and conversation metadata"
    Env     = "local"
  }
}

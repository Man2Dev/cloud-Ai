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
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # Attribute used by GSI
  attribute {
    name = "model_name"
    type = "S"
  }

  # Global Secondary Index to query by model across users
  global_secondary_index {
    name            = "model_index"
    hash_key        = "model_name"
    projection_type = "ALL"
  }

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Track user sessions, model selection, and conversation metadata"
    Env     = "local"
  }
}

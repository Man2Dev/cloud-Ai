# S3 bucket to store user conversation logs
resource "aws_s3_bucket" "chatbot_conversations" {
  bucket = "chatbot-conversations"

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Store user conversation logs"
    Env     = "local"
  }
}

# DynamoDB table to track chatbot sessions
resource "aws_dynamodb_table" "chatbot_sessions" {
  name         = "chatbot-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  tags = {
    Project = "AI-Chatbot"
    Purpose = "Track active user sessions and conversation context"
    Env     = "local"
  }
}


output "s3_bucket_name" {
  value       = aws_s3_bucket.chatbot_conversations.bucket
  description = "S3 bucket used for archived chatbot conversations"
}

output "dynamodb_table_name" {
  value       = aws_dynamodb_table.chatbot_sessions.name
  description = "DynamoDB table storing chatbot session metadata"
}

output "dynamodb_model_gsi" {
  value       = "model_index"
  description = "Global secondary index on DynamoDB table for querying by model_name"
}
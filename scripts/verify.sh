#!/bin/bash

echo "======================================"
echo "🔍 LOCALSTACK INFRASTRUCTURE VERIFICATION"
echo "======================================"

echo -e "\n1 Checking LocalStack Health..."
curl -s http://localhost:4566/_localstack/health | jq

echo -e "\n2 Listing S3 Buckets..."
aws s3 ls --endpoint-url http://localhost:4566

echo -e "\n3 Listing content in the S3 Buckets..."
awslocal s3 ls s3://chatbot-conversations --recursive

echo -e "\n4 Verifying S3 Bucket Details..."
aws s3api head-bucket --bucket chatbot-conversations --endpoint-url http://localhost:4566 && echo "✓ Bucket exists and is accessible"

echo -e "\n5 Listing DynamoDB Tables..."
aws dynamodb list-tables --endpoint-url http://localhost:4566

echo -e "\n6 Describing DynamoDB Table Structure..."
aws dynamodb describe-table --table-name chatbot-sessions --endpoint-url http://localhost:4566 | jq '.Table | {TableName, TableStatus, KeySchema, AttributeDefinitions, GlobalSecondaryIndexes}'

echo -e "\n7 Terraform Outputs..."
terraform output

echo -e "\n======================================"
echo "✅ VERIFICATION COMPLETE"
echo "======================================"

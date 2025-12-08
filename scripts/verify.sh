#!/bin/bash

echo "======================================"
echo "🔍 LOCALSTACK INFRASTRUCTURE VERIFICATION"
echo "======================================"

echo -e "\n1️⃣ Checking LocalStack Health..."
curl -s http://localhost:4566/_localstack/health | jq

echo -e "\n2️⃣ Listing S3 Buckets..."
aws s3 ls --endpoint-url http://localhost:4566

echo -e "\n3️⃣ Verifying S3 Bucket Details..."
aws s3api head-bucket --bucket chatbot-conversations --endpoint-url http://localhost:4566 && echo "✓ Bucket exists and is accessible"

echo -e "\n4️⃣ Listing DynamoDB Tables..."
aws dynamodb list-tables --endpoint-url http://localhost:4566

echo -e "\n5️⃣ Describing DynamoDB Table Structure..."
aws dynamodb describe-table --table-name chatbot-sessions --endpoint-url http://localhost:4566 | jq '.Table | {TableName, TableStatus, KeySchema, AttributeDefinitions, GlobalSecondaryIndexes}'

echo -e "\n6️⃣ Terraform Outputs..."
terraform output

echo -e "\n======================================"
echo "✅ VERIFICATION COMPLETE"
echo "======================================"

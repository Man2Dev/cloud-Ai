# Mid-Term Demo Cheatsheet

## Quick Reference Commands

---

## Part A: Live Demo Steps

### 1. Show Terraform Apply

```bash
# First, show the plan
terraform plan

# Then apply (already deployed, but can show)
terraform apply -auto-approve
```

**Expected Output:**
- S3 bucket: `chatbot-conversations-654654624560`
- DynamoDB table: `chatbot-sessions`
- Lambda function: `telegram-bot`
- API Gateway: `telegram-bot-api`

### 2. Demonstrate Bot Commands (in Telegram)

| Command | What It Shows | Demo Script |
|---------|---------------|-------------|
| `/start` | Bot initialization | "Hi! I'm your AI-powered Telegram assistant" |
| `/help` | Command list | Shows all available commands |
| `/newsession` | Creates session in DynamoDB | Creates UUID, stores in DB |
| `/listsessions` | DynamoDB read operation | Lists all user sessions |
| `/history` | Conversation retrieval | Shows message history |
| `/archive 1` | S3 write operation | Moves session to S3 |
| `/listarchives` | S3 list operation | Shows archived files |
| `/export 1` | S3 read + file send | Downloads archive as JSON |

**Recommended Demo Flow:**
1. Send `/start` - Initialize
2. Send `/help` - Show commands
3. Send `/newsession` - Create session (DynamoDB write)
4. Send some messages - Populate conversation
5. Send `/listsessions` - Show DynamoDB read
6. Send `/history` - Show conversation retrieval
7. Send `/archive` - Move to S3 (demonstrate persistence)
8. Send `/listarchives` - Show S3 listing

### 3. Show DynamoDB Persistence

```bash
# Option 1: Use our script
./scripts/view-data.sh dynamodb

# Option 2: AWS CLI
aws dynamodb scan --table-name chatbot-sessions --output table

# Show specific item
aws dynamodb get-item \
  --table-name chatbot-sessions \
  --key '{"pk": {"N": "136431476"}, "sk": {"S": "MODEL#llama3#SESSION#..."}}' \
  | jq
```

### 4. Show S3 Integration

```bash
# Option 1: Use our script
./scripts/view-data.sh s3

# Option 2: AWS CLI - List bucket contents
aws s3 ls s3://chatbot-conversations-654654624560/ --recursive

# Download and view an archive
aws s3 cp s3://chatbot-conversations-654654624560/archives/USER_ID/SESSION_ID.json - | jq
```

### 5. Architecture Walkthrough

```bash
# Show Lambda function
aws lambda get-function --function-name telegram-bot | jq '.Configuration | {FunctionName, Runtime, Handler, MemorySize, Timeout}'

# Show API Gateway
aws apigateway get-rest-apis | jq '.items[] | {name, id, endpointConfiguration}'

# Show DynamoDB table structure
aws dynamodb describe-table --table-name chatbot-sessions | jq '.Table | {TableName, KeySchema, GlobalSecondaryIndexes}'

# Show S3 bucket
aws s3api get-bucket-tagging --bucket chatbot-conversations-654654624560
```

### 6. Show Terraform Destroy (if requested)

```bash
# WARNING: This will delete all resources!
terraform destroy -auto-approve

# Re-deploy after
terraform apply -auto-approve
./scripts/setup-webhook.sh
```

---

## Part B: Gap Analysis Summary (for slide)

### Best Practices Implemented ✅

1. **Separate Terraform files** - provider.tf, main.tf, outputs.tf
2. **Variable definitions** - With types, descriptions, sensitive marking
3. **Consistent resource tagging** - Project, Purpose, Env on all resources
4. **Dynamic naming** - Account ID in S3 bucket name for uniqueness
5. **Provider version constraints** - Locked AWS provider version
6. **Outputs with descriptions** - All key values exported
7. **DynamoDB best practices** - PAY_PER_REQUEST, TTL enabled, GSIs

### Gaps Identified ❌

1. **No modules** - All resources in single main.tf
2. **No locals block** - Repeated values not centralized
3. **IAM over-permissioned** - LabRole has broad access (AWS Academy limitation)
4. **No environment separation** - Single environment only
5. **No CloudWatch log retention** - Logs never expire
6. **No remote state backend** - Using local state file

### Action Plan for Refactor

| Priority | Task | Timeline |
|----------|------|----------|
| P1 | Create variables.tf (separate from main.tf) | Before next class |
| P1 | Add locals.tf for common tags | Before next class |
| P1 | Add CloudWatch log group with retention | Before next class |
| P2 | Add environment variable for dev/prod | Next sprint |
| P2 | Document ideal IAM policies | Next sprint |
| P3 | Modularize resources | Future |
| P3 | Add remote state backend | Future |

---

## Demo Verification Commands

```bash
# Verify all resources exist
echo "=== Lambda ===" && aws lambda get-function --function-name telegram-bot --query 'Configuration.FunctionName'
echo "=== DynamoDB ===" && aws dynamodb describe-table --table-name chatbot-sessions --query 'Table.TableName'
echo "=== S3 ===" && aws s3api head-bucket --bucket chatbot-conversations-654654624560 && echo "Bucket exists"
echo "=== API Gateway ===" && aws apigateway get-rest-apis --query 'items[?name==`telegram-bot-api`].name'

# Verify webhook
curl -s "https://api.telegram.org/bot$(grep telegram_token terraform.tfvars | cut -d'"' -f2)/getWebhookInfo" | jq '.result.url'
```

---

## Troubleshooting During Demo

### If credentials expire:
```bash
# Check status
aws sts get-caller-identity

# If expired, update ~/.aws/credentials from AWS Academy
```

### If webhook not working:
```bash
./scripts/setup-webhook.sh
```

### If need to see Lambda logs:
```bash
aws logs tail /aws/lambda/telegram-bot --follow
```
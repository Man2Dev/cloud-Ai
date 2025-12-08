# LocalStack AI Chatbot Infrastructure Documentation

This project sets up a **local AWS-like environment** for running an AI chatbot using LocalStack and Terraform. It provisions **S3 buckets** for storing archived chat history and **DynamoDB tables** for managing user sessions and metadata. Users interact with the bot through **Telegram**.

> **⚠️ Status**: Currently in development. Ollama AI integration (backend models) is not yet implemented. Session management, commands, archive features, and Telegram connectivity are functional.

- - -
## Table of Contents

* [Overview](#overview)
* [Architecture Overview](#architecture-overview)
* [Current Features](#current-features)
* [Data Storage](#data-storage)
* [Archive System](#archive-system)
* [DynamoDB Design](#dynamodb-design)
* [Dependencies](#dependencies)
  * [Windows (Scoop)](#windows-scoop)
  * [Fedora Linux (dnf)](#fedora-linux-dnf)
  * [macOS (Homebrew)](#macos-homebrew)
* [Setup Instructions](#setup-instructions)
* [AWS CLI Tools](#aws-cli-tools)
* [Running the Bot](#running-the-bot)
* [Commands](#commands)
* [Project Structure](#project-structure)
* [Verification](#verification)
* [Troubleshooting](#troubleshooting)
* [License](#license)

- - -
## Overview

The project creates a Telegram bot that manages user sessions and stores interaction data in LocalStack. The architecture separates session management from AI processing for flexibility during development.

**Current Scope:**
- ✅ Telegram bot message polling
- ✅ User session creation and management
- ✅ Command handling (`/help`, `/newsession`, `/listsessions`, `/switch`, `/history`, `/echo`)
- ✅ Archive system (`/archive`, `/listarchives`, `/export`, file import)
- ✅ DynamoDB for live session storage
- ✅ S3 for archived session storage
- ⏳ Ollama integration (planned for next phase)

- - -
## Architecture Overview

**Current Flow:**
```
Telegram Bot → Lambda Handler → DynamoDB (Active Sessions)
                             → S3 (Archived Sessions)
```

**Future Flow (with Ollama):**
```
Telegram Bot → Lambda Handler → Ollama API → DynamoDB + S3 (via LocalStack)
```

**Current Process:**
1. Telegram user sends a message to the bot
2. Lambda function polls for updates via `getUpdates`
3. Message is processed (command, chat, or file upload)
4. Active session data is stored in **DynamoDB**
5. Archived sessions are stored in **S3**
6. Response is sent back to Telegram

- - -
## Current Features

Users can interact with the bot using these commands:

| Command | Purpose | Status |
|---------|---------|--------|
| `/start` or `/hello` | Initialize and greet user | ✅ Working |
| `/help` | Show available commands | ✅ Working |
| `/newsession` | Create a new chat session | ✅ Working |
| `/listsessions` | List all user sessions | ✅ Working |
| `/switch <number>` | Switch to a different session | ✅ Working |
| `/history` | Show recent messages in session | ✅ Working |
| `/archive` | List sessions available to archive | ✅ Working |
| `/archive <number>` | Archive a specific session to S3 | ✅ Working |
| `/listarchives` | List archived sessions | ✅ Working |
| `/export <number>` | Export archive as JSON file | ✅ Working |
| Send JSON file | Import archive from file | ✅ Working |
| `/status` | Check Ollama connection | ⏳ Not implemented |
| `/echo <text>` | Echo back text (test command) | ✅ Working |
| Chat messages | Send to AI model | ⏳ Not implemented |

- - -
## Data Storage

### DynamoDB (Active Sessions)
- User sessions with model selection
- Conversation context and recent messages
- Session status (active/inactive)
- Timestamps and metadata

### S3 (Archived Sessions)
- Archived full chat transcripts
- Historical logs for long-term storage
- Exportable/importable JSON format
- User-isolated storage paths

- - -
## Archive System

The archive system allows users to move sessions from DynamoDB to S3, export them as files, and import archives.

### S3 Storage Structure
```
chatbot-conversations/
└── archives/
    └── {user_id}/
        ├── {session_id_1}.json
        ├── {session_id_2}.json
        └── ...
```

Each archive JSON contains:
```json
{
  "user_id": 123456789,
  "session_id": "uuid-string",
  "model_name": "llama3",
  "conversation": [
    {"role": "user", "content": "Hello!", "ts": 1234567890},
    {"role": "assistant", "content": "Hi there!", "ts": 1234567891}
  ],
  "original_sk": "MODEL#llama3#SESSION#uuid",
  "last_message_ts": 1234567891,
  "archived_at": "2024-01-15T10:30:00Z",
  "archive_version": "1.0"
}
```

### Archive Workflow

**Archiving a session:**
1. User runs `/archive` to list available sessions
2. User runs `/archive <number>` to archive specific session
3. Session data is saved to S3 at `archives/{user_id}/{session_id}.json`
4. Session is removed from DynamoDB

**Exporting an archive:**
1. User runs `/listarchives` to see archived sessions
2. User runs `/export <number>` to download specific archive
3. Bot sends JSON file via Telegram

**Importing an archive:**
1. User sends a JSON file to the bot
2. Bot validates the JSON structure
3. Archive is saved to S3 with a new session ID (prevents conflicts)
4. Original metadata is preserved for reference

### Data Isolation
- Each user's archives are stored in their own S3 prefix: `archives/{user_id}/`
- Imported archives receive new session IDs to prevent conflicts
- Users can only access their own archives

- - -
## DynamoDB Design

### Table Name
`chatbot-sessions`

### Keys
* **Partition Key (`pk`)**: Type `N` (number) - Telegram user ID
* **Sort Key (`sk`)**: Type `S` (string) - Either `MODEL#<model_name>#SESSION#<session_id>` for sessions, or `last_update_id` for bot state tracking

### Attributes
| Attribute | Type | Purpose |
|-----------|------|---------|
| `pk` | Number | Telegram user ID (partition key) |
| `sk` | String | Session identifier (sort key) |
| `user_id` | Number | Telegram user ID (denormalized) |
| `chat_id` | String | Telegram chat ID |
| `model_name` | String | Selected model name |
| `session_id` | String | UUID for the session |
| `conversation` | List | Array of message objects `{role, content, ts}` |
| `is_active` | Number | 1 = active, 0 = inactive |
| `last_message_ts` | Number | Unix timestamp of last message |
| `s3_path` | String | S3 path when session is archived (empty initially) |

### Table Structure
```
┌──────────────────────────────────────────────────┐
│          chatbot-sessions (DynamoDB)             │
├──────────────────────────────────────────────────┤
│ pk (N): <telegram_user_id>                       │
│ sk (S): MODEL#<model_name>#SESSION#<session_id>  │
├──────────────────────────────────────────────────┤
│ Attributes:                                      │
│ • user_id, chat_id, model_name, session_id       │
│ • conversation (list of messages)                │
│ • is_active (1 or 0), last_message_ts            │
│ • s3_path (for archived sessions)                │
├──────────────────────────────────────────────────┤
│ GSI: model_index                                 │
│   Hash: model_name | Range: session_id           │
│ GSI: active_sessions_index                       │
│   Hash: is_active | Range: last_message_ts       │
│ TTL: Enabled (attribute: ttl)                    │
└──────────────────────────────────────────────────┘
```

- - -
## Dependencies

### Python Dependencies
Install the AWS CLI local wrapper:
```bash
pip install awscli-local
```

### Windows (Scoop)

Required tools:
* Terraform
* Docker
* Docker Compose

Install via Scoop:
```powershell
scoop install terraform docker docker-compose
```

### Fedora Linux (dnf)

Required tools:
* Terraform
* Docker
* Docker Compose

Install via dnf:
```bash
sudo dnf install -y terraform awscli docker docker-compose
```

Enable and start Docker service:
```bash
sudo systemctl enable --now docker
```

### macOS (Homebrew)

Required tools:
* Terraform
* Docker
* Docker Compose

Install via Homebrew:
```bash
brew install terraform docker docker-compose
```

Ensure Docker Desktop or an alternative is running before starting LocalStack.

- - -
## Setup Instructions

1. **Clone the repository**:
```bash
git clone https://github.com/Man2Dev/cloud-Ai.git
cd cloud-Ai
```

2. **Start LocalStack** using Docker Compose:
```bash
docker compose up -d
```

3. **Configure AWS CLI**:
```bash
aws configure
```

Use placeholder credentials:
```
AWS Access Key ID: test
AWS Secret Access Key: test
Default region name: us-east-1
Default output format: json
```

4. **Configure Telegram Token** (choose one method):

**Option A: Using terraform.tfvars (Recommended)**
```bash
# Copy the example file
cp terraform.tfvars.example terraform.tfvars

# Edit and add your token
nano terraform.tfvars  # or use your preferred editor
```

Set your token in `terraform.tfvars`:
```hcl
telegram_token = "YOUR_TOKEN"
```

**Option B: Using command line variable**
```bash
terraform apply -var="telegram_token=YOUR_TOKEN"
```

**Option C: Using environment variable**
```bash
export TF_VAR_telegram_token="YOUR_TOKEN"
terraform apply
```

5. **Prepare Lambda package** (required for Terraform to zip function):
```bash
# Clean up any existing package
rm -rf package/ lambda_function.zip

# Create package directory
mkdir -p package

# Install dependencies into package/
pip install -r requirements.txt -t ./package

# Copy function code into package/
cp handler.py package/
```

6. **Initialize and apply Terraform**:
```bash
terraform init
terraform apply -auto-approve
```

7. **Test the Lambda function**:
```bash
awslocal lambda invoke --function-name telegram-bot output.json && cat output.json
```

- - -
## AWS CLI Tools

This project uses LocalStack to emulate AWS services locally. There are two ways to interact with LocalStack:

### awslocal (Recommended)

`awslocal` is a wrapper around the AWS CLI that automatically configures the endpoint URL for LocalStack. It's simpler and less error-prone.

**Installation:**
```bash
pip install awscli-local
```

**Usage:**
```bash
# List S3 buckets
awslocal s3 ls

# List DynamoDB tables
awslocal dynamodb list-tables

# Invoke Lambda function
awslocal lambda invoke --function-name telegram-bot output.json

# Describe DynamoDB table
awslocal dynamodb describe-table --table-name chatbot-sessions

# List objects in S3 bucket
awslocal s3 ls s3://chatbot-conversations/

# Get Lambda function info
awslocal lambda get-function --function-name telegram-bot
```

### aws (Standard AWS CLI)

The standard AWS CLI requires manually specifying the LocalStack endpoint URL for every command.

**Usage:**
```bash
# List S3 buckets
aws s3 ls --endpoint-url http://localhost:4566

# List DynamoDB tables
aws dynamodb list-tables --endpoint-url http://localhost:4566

# Invoke Lambda function
aws lambda invoke --function-name telegram-bot output.json --endpoint-url http://localhost:4566

# Describe DynamoDB table
aws dynamodb describe-table --table-name chatbot-sessions --endpoint-url http://localhost:4566

# List objects in S3 bucket
aws s3 ls s3://chatbot-conversations/ --endpoint-url http://localhost:4566

# Get Lambda function info
aws lambda get-function --function-name telegram-bot --endpoint-url http://localhost:4566
```

### Comparison

| Feature | awslocal | aws |
|---------|----------|-----|
| Endpoint configuration | Automatic | Manual (`--endpoint-url`) |
| Command length | Shorter | Longer |
| LocalStack-specific | Yes | No (works with real AWS too) |
| Installation | `pip install awscli-local` | Included with AWS CLI |

**Recommendation:** Use `awslocal` for LocalStack development. Use `aws` with `--endpoint-url` if you need to switch between LocalStack and real AWS frequently.

- - -
## Running the Bot

The Lambda function needs to be invoked repeatedly to poll for new Telegram messages. LocalStack doesn't support event-driven triggers like real AWS, so we use manual polling.

### Single Invocation
```bash
awslocal lambda invoke --function-name telegram-bot output.json && cat output.json
```

### Continuous Polling (Recommended for Development)

Run this loop in the Bash shell to continuously poll for messages:

```bash
while true; do awslocal lambda invoke --function-name telegram-bot out.json >/dev/null 2>&1; sleep 1; done
```

**What this does:**
- Invokes the Lambda function every second
- Suppresses output to keep terminal clean
- Runs until you press `Ctrl+C` to stop

**With visible output:**
```bash
while true; do awslocal lambda invoke --function-name telegram-bot out.json && cat out.json; sleep 1; done
```

**With timestamps:**
```bash
while true; do echo "$(date '+%H:%M:%S') - Polling..."; awslocal lambda invoke --function-name telegram-bot out.json >/dev/null 2>&1; sleep 1; done
```

### Background Polling

Run polling in the background:
```bash
# Start in background
nohup bash -c 'while true; do awslocal lambda invoke --function-name telegram-bot out.json >/dev/null 2>&1; sleep 1; done' &

# Find and stop the background process
ps aux | grep "lambda invoke"
kill <PID>
```

- - -
## Commands

**Verify resources:**
```bash
# List S3 buckets
awslocal s3 ls

# List DynamoDB tables
awslocal dynamodb list-tables

# List archived sessions for a user (replace USER_ID)
awslocal s3 ls s3://chatbot-conversations/archives/USER_ID/

# View Lambda logs
awslocal logs tail /aws/lambda/telegram-bot --follow

# Scan DynamoDB table
awslocal dynamodb scan --table-name chatbot-sessions
```

**Cleanup:**
```bash
terraform destroy -auto-approve
docker compose down
rm -rf package/ lambda_function.zip
```

- - -
## Project Structure

```
.
├── docker-compose.yml          # LocalStack services configuration
├── provider.tf                 # Terraform AWS provider (LocalStack endpoints)
├── main.tf                     # Terraform resources (S3, DynamoDB, IAM, Lambda)
├── outputs.tf                  # Terraform outputs (resource names)
├── terraform.tfvars.example    # Example variables file (copy to terraform.tfvars)
├── terraform.tfvars            # Your local variables (gitignored)
├── requirements.txt            # Python dependencies (requests, boto3)
├── handler.py                  # Lambda handler (Telegram polling, sessions, archives)
├── scripts/
│   ├── demo.py                 # Demo script for testing S3 and DynamoDB
│   └── verify.sh               # Bash script to verify LocalStack health
├── .gitignore                  # Git ignore file
├── LICENSE                     # GPL v3 License
└── README.md                   # This documentation
```

- - -
## Verification

After deployment, verify resources exist:

```bash
# Check S3 bucket
awslocal s3 ls

# Check DynamoDB table
awslocal dynamodb describe-table --table-name chatbot-sessions | jq '.Table.TableStatus'

# Check Lambda function
awslocal lambda get-function --function-name telegram-bot | jq '.Configuration.FunctionName'

# Check Lambda environment variables (verify token is set)
awslocal lambda get-function-configuration --function-name telegram-bot | jq '.Environment.Variables'
```

Or use the provided script:
```bash
bash scripts/verify.sh
```

- - -
## Troubleshooting

* **Port conflicts**: Stop other containers using conflicting ports.
* **Terraform connection errors**: Ensure LocalStack container is running (`docker compose up -d`).
* **AWS CLI timeouts**: Use `awslocal` or add `--endpoint-url http://localhost:4566` for all commands.
* **Reset LocalStack data**: Stop LocalStack and delete the `localstack-data/` folder, then restart.
* **Docker permissions (Linux)**: Add your user to the `docker` group and re-login.
* **Lambda invocation errors**: Verify the Telegram token is set correctly in `terraform.tfvars`.
* **Telegram messages not received**: Ensure the polling loop is running.
* **Archive import fails**: Ensure the JSON file has a valid `conversation` array field.
* **S3 access errors**: Verify the S3 bucket exists with `awslocal s3 ls`.
* **"No module named requests"**: Rebuild the Lambda package with `pip install -r requirements.txt -t ./package`.

- - -
## License

This project is licensed under **GNU General Public License v3.0 or later (GPLv3+)**. See [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) for full details.

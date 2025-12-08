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

4. **Prepare Lambda package** (required for Terraform to zip function):
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

5. **Initialize and apply Terraform** (pass your Telegram token):
```bash
terraform init
terraform apply -auto-approve -var="telegram_token=YOUR_TELEGRAM_BOT_TOKEN"
```

Replace `YOUR_TELEGRAM_BOT_TOKEN` with your actual Telegram bot token from BotFather.

6. **Test the Lambda function**:
```bash
awslocal lambda invoke --function-name telegram-bot output.json && cat output.json
```

**UNIX command to loop invoke command**
```bash
while true; do awslocal lambda invoke --function-name telegram-bot out.json >/dev/null 2>&1; sleep 1; done
```


This invokes the Lambda function, which polls Telegram for new messages once. Repeat the command to process more messages.

- - -
## Commands

**Verify resources:**
```bash
# List S3 buckets
aws s3 ls --endpoint-url http://localhost:4566

# List DynamoDB tables
aws dynamodb list-tables --endpoint-url http://localhost:4566

# List archived sessions for a user (replace USER_ID)
aws s3 ls s3://chatbot-conversations/archives/USER_ID/ --endpoint-url http://localhost:4566

# View Lambda logs
awslocal logs tail /aws/lambda/telegram-bot --follow
```

**Cleanup:**
```bash
terraform destroy -auto-approve
docker compose down
rm -rf package/ lambda_function.zip
```

- - -
## Project Structure

* `docker-compose.yml` — LocalStack services configuration
* `provider.tf` — Terraform AWS provider configuration (LocalStack endpoints)
* `main.tf` — Terraform resources (S3, DynamoDB, IAM, Lambda)
* `outputs.tf` — Terraform outputs (resource names)
* `requirements.txt` — Python dependencies (requests, boto3)
* `handler.py` — Lambda handler (Telegram polling, session management, archive commands)
* `scripts/demo.py` — Demo script for testing S3 and DynamoDB operations
* `scripts/verify.sh` — Bash script to verify LocalStack health and resources
* `.gitignore` — Git ignore file
* `README.md` — This documentation

- - -
## Verification

After deployment, verify resources exist:

```bash
# Check S3 bucket
aws s3 ls --endpoint-url http://localhost:4566

# Check DynamoDB table
aws dynamodb describe-table --table-name chatbot-sessions \
  --endpoint-url http://localhost:4566 | jq '.Table.TableStatus'

# Check Lambda function
aws lambda get-function --function-name telegram-bot \
  --endpoint-url http://localhost:4566 | jq '.Configuration.FunctionName'
```

Or use the provided script:
```bash
bash scripts/verify.sh
```

- - -
## Troubleshooting

* **Port conflicts**: Stop other containers using conflicting ports.
* **Terraform connection errors**: Ensure LocalStack container is running (`docker compose up -d`).
* **AWS CLI timeouts**: Use `--endpoint-url http://localhost:4566` for all commands.
* **Reset LocalStack data**: Stop LocalStack and delete the `localstack-data/` folder, then restart.
* **Docker permissions (Linux)**: Add your user to the `docker` group and re-login.
* **Lambda invocation errors**: Verify the Telegram token is set correctly in `main.tf`.
* **Telegram messages not received**: Check that the polling is working via Lambda logs.
* **Archive import fails**: Ensure the JSON file has a valid `conversation` array field.
* **S3 access errors**: Verify the S3 bucket exists with `aws s3 ls --endpoint-url http://localhost:4566`.

- - -
## License

This project is licensed under **GNU General Public License v3.0 or later (GPLv3+)**. See [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) for full details.

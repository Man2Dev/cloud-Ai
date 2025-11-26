# LocalStack AI Chatbot Infrastructure Documentation

This project sets up a **local AWS-like environment** for running an AI chatbot using LocalStack and Terraform. It provisions **S3 buckets** for storing archived chat history and **DynamoDB tables** for managing user sessions and metadata. Users interact with the bot through **Telegram**.

> **⚠️ Status**: Currently in development. Ollama AI integration (backend models) is not yet implemented. Session management, commands, and Telegram connectivity are functional.

- - -
## Table of Contents

* [Overview](#overview)
* [Architecture Overview](#architecture-overview)
* [Current Features](#current-features)
* [Data Storage](#data-storage)
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
- ✅ DynamoDB for live session storage
- ⏳ Ollama integration (planned for next phase)
- ⏳ S3 archival of completed sessions (planned)

- - -
## Architecture Overview

**Current Flow:**
```
Telegram Bot → Lambda Handler → DynamoDB (Session Storage)
```

**Future Flow (with Ollama):**
```
Telegram Bot → Lambda Handler → Ollama API → DynamoDB + S3 (via LocalStack)
```

**Current Process:**
1. Telegram user sends a message to the bot
2. Lambda function polls for updates via `getUpdates`
3. Message is processed (command or chat)
4. Session data is stored in **DynamoDB**
5. Response is sent back to Telegram

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
| `/status` | Check Ollama connection | ⏳ Not implemented |
| `/echo <text>` | Echo back text (test command) | ✅ Working |
| Chat messages | Send to AI model | ⏳ Not implemented |

- - -
## Data Storage

User data is stored in **DynamoDB** (`chatbot-sessions` table), not S3.

**DynamoDB (Live Data):**
- User sessions with model selection
- Conversation context and recent messages
- Session status (active/archived)
- Timestamps and metadata

**S3 (Planned - Future):**
- Archived full chat transcripts (when sessions are completed or archived)
- Historical logs for long-term storage
- Cheaper storage for infrequently accessed data

Current implementation stores everything in DynamoDB. S3 integration will be added when session archival is implemented.

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
| `is_active` | Number | 1 = active, 0 = archived |
| `last_message_ts` | Number | Unix timestamp of last message |
| `s3_path` | String | S3 path when session is archived (empty initially) |

### Table Structure
```
┌──────────────────────────────────────────────────┐
│          chatbot-sessions (DynamoDB)             │
├──────────────────────────────────────────────────┤
│ pk (N): <telegram_user_id>                       │
│ sk (S): MODEL#<model_name>#SESSION#<session_id> │
├──────────────────────────────────────────────────┤
│ Attributes:                                      │
│ • user_id, chat_id, model_name, session_id      │
│ • conversation (list of messages)               │
│ • is_active (1 or 0), last_message_ts           │
│ • s3_path (for archived sessions)               │
├──────────────────────────────────────────────────┤
│ GSI: model_index                                 │
│   Hash: model_name | Range: session_id          │
│ GSI: active_sessions_index                       │
│   Hash: is_active | Range: last_message_ts      │
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

4. **Create `.env.tfvars` file** with your Telegram token:
```bash
cat > .env.tfvars << EOF
telegram_token = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
EOF
```

Replace `YOUR_TELEGRAM_BOT_TOKEN_HERE` with your actual token from BotFather.

> **⚠️ Important**: The `.env.tfvars` file contains sensitive information (your Telegram bot token). 
> - This file is already added to `.gitignore` and should **never** be committed to version control
> - Keep this file secure and do not share it
> - If you accidentally expose your token, regenerate it immediately via BotFather

To get your Telegram token:
1. Open Telegram and search for `@BotFather`
2. Create a new bot with `/newbot`
3. Copy the token provided (format: `123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh`)
4. Paste it into `.env.tfvars`

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
terraform apply -auto-approve -var-file=".env.tfvars"
```

Terraform will automatically load variables from `.env.tfvars`.

6. **Test the Lambda function**:
```bash
awslocal lambda invoke --function-name telegram-bot output.json && cat output.json
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
* `handler.py` — Lambda handler (Telegram polling, session management, commands)
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

- - -
## License

This project is licensed under **GNU General Public License v3.0 or later (GPLv3+)**. See [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) for full details.
# LocalStack AI Chatbot Infrastructure Documentation

This project sets up a **local AWS-like environment** for running an AI chatbot
for users using LocalStack and Terraform. It provisions **S3 buckets** for
storing chat history and **DynamoDB tables** for managing live sessions and
metadata. Users can interact with multiple models through Telegram, with the
backend powered by **Ollama**.

- - -
## Table of Contents

* [Overview](#overview)
* [Architecture Overview](#architecture-overview)
* [DynamoDB and S3 Design](#dynamodb-and-s3-design)
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

The project emulates AWS services locally to allow users to interact with AI
chatbots through Telegram. The backend communicates with the **Ollama API** to
run multiple AI models and stores user interactions in DynamoDB and S3.

* **S3 Bucket (`chatbot-conversations`)**: Stores chat transcripts, logs, and
  archived sessions.
* **DynamoDB Table (`chatbot-sessions`)**: Stores active user sessions, context,
  and model metadata.

Using LocalStack, all resources are created locally and accessible via AWS CLI
or Terraform without requiring a real AWS account.

- - -
## Architecture Overview

```
Telegram Bot → Backend Server → Ollama API → DynamoDB + S3 (via LocalStack)
```
**Flow:**

1.  A Telegram user sends a message to the bot.
2.  The backend receives it and determines which **Ollama model** to use (e.g.,
    llama3, mistral, phi3).
3.  The message is sent to the **Ollama API** (`
    http://localhost:11434/api/generate`).
4.  The model response is stored temporarily in **DynamoDB**.
5.  When a session ends or grows large, it’s archived to **S3** for long-term
    storage.

This setup allows multiple Telegram users to chat with different AI models
simultaneously, maintaining their context across sessions.

- - -
## DynamoDB and S3 Design

### Table Name

`ChatbotSessions`

### Purpose

To store session state, model selection, and conversation context for each
Telegram user interacting with Ollama models through the chatbot.

- - -
### Keys

* **Partition Key (`PK`)**: `USER#\<telegram_user_id>` → Groups all sessions by
  user.
* **Sort Key (`SK`)**: `MODEL#\<model_name>#SESSION#<session_id>` → Allows
  multiple models and sessions per user.

### Attributes

* `user_id` → Telegram user ID
* `chat_id` → Telegram chat ID
* `model_name` → Ollama model used for the session
* `session_id` → Unique session identifier
* `conversation` → List of recent messages (JSON array or serialized text)
* `last_message_ts` → Timestamp of the last message
* `status` → Active/closed session
* `ollama_endpoint` → API endpoint for Ollama (e.g., `http://localhost:11434`)
* `s3_path` → Path to archived session in S3

- - -
### UML Diagram Representation

```text
+---------------------------------------------+
|               ChatbotSessions               |
+---------------------------------------------+
| PK: USER#<user_id>                          |
| SK: MODEL#<model_name>#SESSION#<session_id> |
+---------------------------------------------+
| user_id                                     |
| chat_id                                     |
| model_name                                  |
| session_id                                  |
| conversation                                |
| last_message_ts                             |
| status                                      |
| ollama_endpoint                             |
| s3_path                                     |
+---------------------------------------------+
```
- - -
### S3 Bucket Design

#### Bucket Name

`chatbot-conversations`

#### Purpose

Stores archived session transcripts, logs, and outputs for each user and model.

#### Structure

```
s3://chatbot-conversations/
│
├── <user_id>/
│   ├── model_<model_name>/
│   │   ├── session_<session_id>.json
│   │   └── session_<session_id>.txt
```
Each file can include:

* The full chat transcript.
* The model used.
* Ollama parameters (temperature, tokens, etc.).
* User metadata and timestamps.

- - -
### Why Use DynamoDB + S3 Together?


|Data Type                  |Stored In|Reason                                 |
|---------------------------|---------|---------------------------------------|
|Current session context    |**DynamoDB**|Fast lookups, limited data size        |
|Chat metadata              |**DynamoDB**|Indexed and queryable                  |
|Archived full chat history |**S3**   |Cheaper, no size limits                |
|Ollama logs and transcripts|**S3**   |Ideal for large, infrequent access data|

**DynamoDB = Live data** **S3 = History and archives**

- - -
## Dependencies

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

1.  **Clone the repository**:

```bash
git clone https://github.com/Man2Dev/cloud-Ai.git
cd cloud-Ai
```
2.  **Start LocalStack** using Docker Compose:

```bash
docker compose up -d
```
3.  **Configure AWS CLI**:

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
4.  Prepare Lambda package (required) Terraform zips the contents of `package/`
    to create `lambda_function.zip`. Do not install requirements globally,
    install them into `package/`.

```bash
# Clean up any existing package and zip
rm -rf package/ lambda_function.zip


# Create package dir
mkdir -p package


# Install dependencies into package/
pip install -r requirements.txt -t ./package


# Copy function code into package/
cp handler.py package/
```
5.  **Deploy & Test**:
6.  Initialize and apply Terraform (pass your Telegram token):

```bash
terraform init
terraform apply -auto-approve -var="telegram_token=YOUR_TELEGRAM_BOT_TOKEN"
```
2.  Invoke Lambda manually (polling model) Use awslocal (recommended) to invoke
    the function this triggers the handler to poll Telegram `getUpdates` once
    per invoke.

```bash
awslocal lambda invoke --function-name telegram-bot output.json && cat output.json
```
3.  Typical test flow
- Send `/hello`, `/help`, or `/echo foo` to your Telegram bot
- Run the awslocal invoke command above
- Confirm the bot replied in Telegram and check `output.json` and Lambda logs

- - -
## Commands

* **Verify resources**: `aws s3 ls --endpoint-url http://localhost:4566` and `
  aws dynamodb list-tables --endpoint-url http://localhost:4566` and `awslocal
  logs tail /aws/lambda/telegram-bot --follow`
* **Cleanup**: `terraform destroy -auto-approve` and `docker compose down` and `
  rm -rf package/ lambda_function.zip`

- - -
## Project Structure

* `docker-compose.yml` — LocalStack services configuration (already in repo)
* `provider.tf` — Terraform AWS provider configuration
* `main.tf` — Terraform resources for S3, DynamoDB, IAM roles/policies, and
  Lambda function
* `requirements.txt` — Python dependencies for the Lambda function (e.g.,
  requests, boto3)
* `outputs.tf` — Terraform outputs (e.g., bucket names, table names)
* `handler.py` — Lambda handler code for polling Telegram updates and processing
  messages
* `localstack-data/` — optional persistent data volume
* `README.md` — documentation

- - -
## Verification

After deployment, confirm resources exist:

* List S3 buckets locally via AWS CLI to ensure conversation logs are stored
* List DynamoDB tables locally via AWS CLI to ensure sessions are tracked
* Check Terraform outputs for resource names

- - -
## Troubleshooting

* **Port conflicts**: Stop other containers using conflicting ports.
* **Terraform connection errors**: Ensure LocalStack container is running.
* **AWS CLI timeouts**: Use `\--endpoint-url http://localhost:4566` for all
  commands.
* **Reset LocalStack data**: Stop LocalStack and delete the `localstack-data/`
  folder.
* **Docker permissions (Linux)**: Add your user to the `docker` group and
  re-login.

- - -
## License

This project is licensed under **GNU General Public License v3.0 or later (GPLv3+)**
. See [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) for full
details.


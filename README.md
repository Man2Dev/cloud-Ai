# LocalStack AI Cloud Infrastructure Documentation

This project sets up a **local AWS-like environment** for AI chatbot development using LocalStack and Terraform.
It provisions **S3 buckets** for chatbot training data and **DynamoDB tables** for user session management. All resources run locally and can be managed via AWS CLI and Terraform.

---

## Table of Contents

* [Overview](#overview)
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

---

## Overview

The project emulates AWS services locally to allow development and testing of an AI chatbot.

* **S3 Bucket (`chatbot-training-data`)**: Stores training datasets, logs, and other chatbot files.
* **DynamoDB Table (`chatbot-sessions`)**: Stores active chatbot sessions and conversation context.

Using LocalStack, all resources are created locally and accessible via AWS CLI or Terraform without requiring a real AWS account.

---

## Dependencies

### Windows (Scoop)

Required tools:

* Terraform
* AWS CLI
* Docker
* Docker Compose

Install via Scoop:

```powershell
scoop install terraform awscli docker docker-compose
```

### Fedora Linux (dnf)

Required tools:

* Terraform
* AWS CLI
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
* AWS CLI
* Docker
* Docker Compose

Install via Homebrew:

```bash
brew install terraform awscli docker docker-compose
```

Ensure Docker Desktop or an alternative is running before starting LocalStack.

---

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

4. **Deploy resources using Terraform**:

```bash
terraform init
terraform apply -auto-approve
```

---

## Commands

* **Clone repository**: `git clone ...`
* **Start LocalStack**: `docker compose up -d`
* **Configure AWS CLI**: `aws configure`
* **Deploy with Terraform**: `terraform init` and `terraform apply -auto-approve`
* **Verify resources**: `aws s3 ls --endpoint-url http://localhost:4566` and `aws dynamodb list-tables --endpoint-url http://localhost:4566`
* **Cleanup**: `terraform destroy -auto-approve` and `docker compose down`

---

## Project Structure

* `docker-compose.yml` — LocalStack services configuration (already in repo)
* `provider.tf` — Terraform AWS provider configuration
* `main.tf` — Terraform resources for S3 and DynamoDB
* `outputs.tf` — Terraform outputs
* `localstack-data/` — optional persistent data volume
* `README.md` — documentation

---

## Verification

After deployment, confirm resources exist:

* List S3 buckets locally via AWS CLI
* List DynamoDB tables locally via AWS CLI
* Check Terraform outputs for resource names

---

## Troubleshooting

* **Port conflicts**: Stop other containers using conflicting ports.
* **Terraform connection errors**: Ensure LocalStack container is running.
* **AWS CLI timeouts**: Use `--endpoint-url http://localhost:4566` for all commands.
* **Reset LocalStack data**: Stop LocalStack and delete the `localstack-data/` folder.
* **Docker permissions (Linux)**: Add your user to the `docker` group and re-login.

---

## License

This project is licensed under **GNU General Public License v3.0 or later (GPLv3+)**.
See [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html) for full details.

# Contributing Guide

## Branch Strategy

This project follows a **Git Flow** branching strategy:

```
main (production)
  │
  ├── dev (development/staging)
  │     │
  │     ├── feature/new-feature
  │     ├── bugfix/fix-issue
  │     └── ...
  │
  └── hotfix/critical-fix (emergency production fixes)
```

### Branch Types

| Branch | Purpose | Base | Merges To |
|--------|---------|------|-----------|
| `main` | Production-ready code | - | - |
| `dev` | Development/staging | `main` | `main` |
| `feature/*` | New features | `dev` | `dev` |
| `bugfix/*` | Bug fixes | `dev` | `dev` |
| `hotfix/*` | Critical production fixes | `main` | `main` & `dev` |

### Workflow

1. **Start new work:**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-new-feature
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push and create PR:**
   ```bash
   git push -u origin feature/my-new-feature
   # Create PR to dev branch on GitHub
   ```

4. **After PR approval:**
   - Merge to `dev` for testing
   - After testing, create PR from `dev` to `main`

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(lambda): add session export command
fix(dynamodb): handle missing session gracefully
docs(readme): update deployment instructions
refactor(terraform): move variables to separate file
```

## CI/CD Pipeline

### Automated Checks (on every push/PR)

1. **Terraform Validate** - Syntax and configuration validation
2. **Python Lint** - Code quality check with flake8
3. **Security Scan** - Checkov for Terraform security best practices
4. **PR Check** - Branch naming and sensitive data detection

### Manual Deployment

Deployments are triggered manually via GitHub Actions:

1. Go to **Actions** > **Deploy to AWS**
2. Click **Run workflow**
3. Select environment (`dev` or `prod`)
4. Click **Run workflow**

### Required Secrets

Configure these in **Settings** > **Secrets and variables** > **Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS Academy access key |
| `AWS_SECRET_ACCESS_KEY` | AWS Academy secret key |
| `AWS_SESSION_TOKEN` | AWS Academy session token |
| `TELEGRAM_TOKEN` | Telegram bot token |
| `LAB_ROLE_ARN` | AWS Academy LabRole ARN |

## Local Development

### Setup

```bash
# Clone and setup
git clone https://github.com/Man2Dev/cloud-Ai.git
cd cloud-Ai
git checkout dev

# Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Build Lambda package
mkdir -p package
pip install -r requirements.txt -t ./package
cp handler.py package/
```

### Deploy Locally

```bash
# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply

# Setup webhook
./scripts/setup-webhook.sh
```

### Verify

```bash
# View stored data
./scripts/view-data.sh

# Check logs
aws logs tail /aws/lambda/telegram-bot --follow
```

## Code Review Checklist

Before merging a PR, ensure:

- [ ] Terraform validates successfully (`terraform validate`)
- [ ] Terraform is formatted (`terraform fmt`)
- [ ] No sensitive data in code
- [ ] Variables have descriptions and validation
- [ ] Resources have appropriate tags
- [ ] README updated if needed
- [ ] Tests pass (if applicable)
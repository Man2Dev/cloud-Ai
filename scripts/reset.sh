#!/bin/bash
set -euo pipefail

###############################################
# CLEAN UP OLD DEPLOYMENT
###############################################

echo "Removing objects from S3 bucket..."
awslocal s3 rm s3://chatbot-conversations --recursive || true

echo "Destroying existing Terraform infrastructure..."
terraform destroy -auto-approve || true

echo "Cleaning old build artifacts..."
rm -rf package/ lambda_function.zip

###############################################
# REBUILD LAMBDA PACKAGE
###############################################

echo "Rebuilding Lambda deployment package..."
mkdir -p package

echo "Installing Python dependencies into package/..."
pip install -r requirements.txt -t ./package

echo "Copying handler.py into package..."
cp handler.py package/

###############################################
# TERRAFORM DEPLOY
###############################################

echo "Initializing Terraform..."
terraform init

echo "Applying Terraform..."
terraform apply -auto-approve

###############################################
# LAMBDA INVOKE LOOP
###############################################

echo "Starting Lambda invoke loop. Press CTRL+C to exit."

while true; do
    awslocal lambda invoke \
        --function-name telegram-bot out.json > /dev/null

    echo "Lambda output:"
    cat out.json | jq

    sleep 1
done


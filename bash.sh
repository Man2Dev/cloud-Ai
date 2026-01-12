#!/bin/bash

TOKEN=$(grep telegram_token terraform.tfvars | sed 's/.*"\(.*\)".*/\1/')
URL=$(terraform output -raw api_gateway_url)

# Set webhook
curl -s "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${URL}" | jq

# Verify
curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo" | jq

# Test bot
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | jq

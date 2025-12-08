import os
import json
import boto3
from datetime import datetime

# Configure DynamoDB for LocalStack
# Use "localhost" if running test script on host;
# Use "host.docker.internal" only if Lambda runs inside Docker (e.g., via LocalStack)
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url="http://localhost:4566",  # ← CHANGED FOR LOCAL TESTING
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

# Configure S3 for LocalStack
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",  # ← CHANGED FOR LOCAL TESTING
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

S3_BUCKET = "chatbot-conversations"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "fake_token_for_testing")
USERS_TABLE = "chatbot-users"
users_table = dynamodb.Table(USERS_TABLE)


def download_telegram_file(file_id, token):
    """Mock file download for local testing — avoids timeout"""
    print(f"[DEV] Mock download for file_id={file_id}")
    return b"Mock file content for local testing"


def lambda_handler(event, context):
    # === Parse event safely ===
    try:
        body = event.get("body")
        if not body:
            return {"statusCode": 200, "body": "No message"}
        
        if isinstance(body, str):
            body = json.loads(body)
        
        message = body.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        text = message.get("text", "").strip()
        
        if not chat_id or not user_id:
            return {"statusCode": 200, "body": "Invalid message"}
            
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, AttributeError):
        return {"statusCode": 200, "body": "Invalid format"}

    # === Handle file uploads (photo or document) ===
    if "photo" in message:
        file_id = message["photo"][-1]["file_id"]
        file_name = f"photo_{file_id}.jpg"
        file_bytes = download_telegram_file(file_id, TELEGRAM_TOKEN)
        s3_key = f"{user_id}/{file_name}"
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_bytes)
        return {"statusCode": 200, "body": f"✅ Photo saved as {file_name}"}

    if "document" in message:
        doc = message["document"]
        file_id = doc["file_id"]
        file_name = doc.get("file_name", f"doc_{file_id}")
        file_bytes = download_telegram_file(file_id, TELEGRAM_TOKEN)
        s3_key = f"{user_id}/{file_name}"
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_bytes)
        return {"statusCode": 200, "body": f"✅ Document saved as {file_name}"}

    # === Handle text commands ===
    if not text.startswith('/'):
        return {"statusCode": 200, "body": "Use /help for commands"}

    parts = text.split(" ", 2)
    cmd = parts[0].lower()

    if cmd == "/start":
        return {"statusCode": 200, "body": "Welcome! Use /save, /get, /list, /history, /delete, /help"}

    elif cmd == "/help":
        return {"statusCode": 200, "body": "/save <key> <value> - Save data\n/get <key> - Retrieve data\n/list - List keys\n/history - Show all data\n/delete <key> - Delete data\n/help - This message"}

    elif cmd == "/save" and len(parts) >= 3:
        key, value = parts[1], parts[2]
        users_table.put_item(
            Item={
                "pk": int(user_id),
                "sk": key,
                "value": value,
                "timestamp": int(datetime.now().timestamp())
            }
        )
        return {"statusCode": 200, "body": f"Saved '{key}' = '{value}'"}

    elif cmd == "/get" and len(parts) == 2:
        key = parts[1]
        resp = users_table.get_item(Key={"pk": int(user_id), "sk": key})
        if "Item" in resp:
            return {"statusCode": 200, "body": f"{key} = {resp['Item']['value']}"}
        else:
            return {"statusCode": 200, "body": f"No data for '{key}'"}

    elif cmd == "/list":
        resp = users_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(int(user_id))
        )
        items = resp.get("Items", [])
        if items:
            keys = [f"- {item['sk']}" for item in items]
            return {"statusCode": 200, "body": "Your keys:\n" + "\n".join(keys)}
        else:
            return {"statusCode": 200, "body": "No saved data"}

    elif cmd == "/history":
        resp = users_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(int(user_id))
        )
        items = resp.get("Items", [])
        if items:
            sorted_items = sorted(items, key=lambda x: x["timestamp"], reverse=True)
            lines = [f"• {item['sk']} = {item['value']}" for item in sorted_items]
            return {"statusCode": 200, "body": "Your history:\n" + "\n".join(lines)}
        else:
            return {"statusCode": 200, "body": "No saved data"}

    elif cmd == "/delete" and len(parts) == 2:
        key = parts[1]
        users_table.delete_item(Key={"pk": int(user_id), "sk": key})
        return {"statusCode": 200, "body": f"Deleted '{key}'"}

    else:
        return {"statusCode": 200, "body": "Unknown command. Use /help"}
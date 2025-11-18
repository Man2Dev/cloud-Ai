import os
import json
import boto3
from datetime import datetime

# Configure DynamoDB with LocalStack endpoint that works inside Lambda containers
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url="http://host.docker.internal:4566",  # This works inside Lambda containers
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

USERS_TABLE = "chatbot-users"
users_table = dynamodb.Table(USERS_TABLE)

def lambda_handler(event, context):
    try:
        body = event.get("body")
        if not body:
            return {"statusCode": 200, "body": "No message"}
        
        if isinstance(body, str):
            body = json.loads(body)
        
        message = body.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        
        if not chat_id or not text:
            return {"statusCode": 200, "body": "Invalid message"}
            
    except:
        return {"statusCode": 200, "body": "Invalid format"}

    if not text.startswith('/'):
        return {"statusCode": 200, "body": "Use /help for commands"}

    parts = text.split(" ", 2)
    cmd = parts[0].lower()

    if cmd == "/start":
        return {"statusCode": 200, "body": "Welcome! Use /save, /get, /list, /history, /delete, /help"}

    elif cmd == "/help":
        return {"statusCode": 200, "body": "/save <key> <value> - Save data\\n/get <key> - Retrieve data\\n/list - List keys\\n/history - Show all data\\n/delete <key> - Delete data\\n/help - This message"}

    elif cmd == "/save" and len(parts) >= 3:
        key, value = parts[1], parts[2]
        users_table.put_item(
            Item={
                "pk": int(message["from"]["id"]),
                "sk": key,
                "value": value,
                "timestamp": int(datetime.now().timestamp())
            }
        )
        return {"statusCode": 200, "body": f"Saved '{key}' = '{value}'"}

    elif cmd == "/get" and len(parts) == 2:
        key = parts[1]
        resp = users_table.get_item(Key={"pk": int(message["from"]["id"]), "sk": key})
        if "Item" in resp:
            return {"statusCode": 200, "body": f"{key} = {resp['Item']['value']}"}
        else:
            return {"statusCode": 200, "body": f"No data for '{key}'"}

    elif cmd == "/list":
        resp = users_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(int(message["from"]["id"]))
        )
        items = resp.get("Items", [])
        if items:
            keys = [f"- {item['sk']}" for item in items]
            return {"statusCode": 200, "body": "Your keys:\\n" + "\\n".join(keys)}
        else:
            return {"statusCode": 200, "body": "No saved data"}

    elif cmd == "/history":
        resp = users_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(int(message["from"]["id"]))
        )
        items = resp.get("Items", [])
        if items:
            sorted_items = sorted(items, key=lambda x: x["timestamp"], reverse=True)
            lines = [f"• {item['sk']} = {item['value']}" for item in sorted_items]
            return {"statusCode": 200, "body": "Your \\n" + "\\n".join(lines)}
        else:
            return {"statusCode": 200, "body": "No saved data"}

    elif cmd == "/delete" and len(parts) == 2:
        key = parts[1]
        users_table.delete_item(
            Key={"pk": int(message["from"]["id"]), "sk": key}
        )
        return {"statusCode": 200, "body": f"Deleted '{key}'"}

    else:
        return {"statusCode": 200, "body": "Unknown command. Use /help"}

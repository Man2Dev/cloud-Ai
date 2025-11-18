import os
import json
import time
import requests
import boto3
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key

# Load environment variables from .env file
load_dotenv()

# -------------------- Configuration --------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8020228066:AAHbaJINkzWO5at_6azHEyN9lfxAJm_LvtE")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:4566")
OFFSET_TABLE_NAME = os.getenv("DYNAMODB_TABLE", "chatbot-sessions")
USER_TABLE_NAME = os.getenv("USER_TABLE", "user-data")

# -------------------- DynamoDB Setup --------------------
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=DYNAMODB_ENDPOINT,
    region_name="us-east-1"
)

offset_table = dynamodb.Table(OFFSET_TABLE_NAME)
user_table = dynamodb.Table(USER_TABLE_NAME)

OFFSET_PK = 0
OFFSET_SK = "last_update_id"

# -------------------- DynamoDB Helpers --------------------
def get_last_offset() -> int:
    try:
        resp = offset_table.get_item(Key={"pk": OFFSET_PK, "sk": OFFSET_SK})
        return int(resp.get("Item", {}).get("last_offset", 0))
    except Exception as e:
        print(f"Error fetching offset: {e}")
        return 0

def save_offset(update_id: int):
    try:
        offset_table.put_item(
            Item={
                "pk": OFFSET_PK,
                "sk": OFFSET_SK,
                "last_offset": update_id,
                "last_updated_ts": int(time.time())
            }
        )
        print(f"Saved offset: {update_id}")
    except Exception as e:
        print(f"Error saving offset: {e}")

def store_user_data(user_id: int, text: str):
    ts = int(time.time())
    try:
        user_table.put_item(Item={
            "user_id": str(user_id),
            "timestamp": ts,
            "message_text": text
        })
        print(f"Stored data for user {user_id}: {text}")
    except Exception as e:
        print(f"Error storing user data: {e}")

def get_user_data(user_id: int):
    try:
        resp = user_table.query(
            KeyConditionExpression=Key('user_id').eq(str(user_id))
        )
        return resp.get("Items", [])
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return []

# -------------------- Telegram Helpers --------------------
def poll_messages(offset: int = 0) -> Dict[str, Any]:
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "TELEGRAM_TOKEN not set"}
    try:
        params = {"limit": 5, "timeout": 0}
        if offset > 0:
            params["offset"] = offset
        resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_message(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    if not TELEGRAM_TOKEN:
        return None
    try:
        resp = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

# -------------------- Message Handler --------------------
def handle_message(text: str, chat_id: int, update_id: int) -> str:
    if not text or not text.strip():
        send_message(chat_id, "No text received.")
        return "no_text"

    cmd, *payload = text.strip().split(" ", 1)
    cmd = cmd.lower()
    payload_text = payload[0].strip() if payload else ""

    print(f"Handling update_id={update_id}, command={cmd}")

    if cmd == "/hello":
        send_message(chat_id, "Hello! 👋 I'm your demo bot.")
        return "hello"

    if cmd == "/help":
        send_message(chat_id, "Commands:\n/hello\n/help\n/echo <text>\n/store <text>\n/mydata")
        return "help"

    if cmd == "/echo":
        send_message(chat_id, payload_text if payload_text else "Usage: /echo <text>")
        return "echo"

    # -------------------- New Assignment Commands --------------------
    if cmd == "/store":
        if not payload_text:
            send_message(chat_id, "Usage: /store <text>")
            return "store_missing_text"
        store_user_data(chat_id, payload_text)
        send_message(chat_id, f"Stored your data: {payload_text}")
        return "store"

    if cmd == "/mydata":
        items = get_user_data(chat_id)
        if not items:
            send_message(chat_id, "No data stored yet.")
            return "mydata_empty"
        # Sort by timestamp
        items_sorted = sorted(items, key=lambda x: x["timestamp"])
        msg = "\n".join([f"- {i['message_text']}" for i in items_sorted])
        send_message(chat_id, f"Your stored data:\n{msg}")
        return "mydata"

    send_message(chat_id, "Unknown command. Send /help for available commands.")
    return "unknown"

# -------------------- Main Loop --------------------
def lambda_handler(event=None, context=None):
    try:
        last_offset = get_last_offset()
        result = poll_messages(last_offset)
        if not result.get("ok"):
            print(f"Telegram API error: {result.get('error')}")
            return {"statusCode": 400, "body": result}

        updates = result.get("result", [])
        if not updates:
            return {"statusCode": 200, "body": "No messages"}

        max_update_id = last_offset
        processed = []

        for update in updates:
            update_id = update.get("update_id", 0)
            if last_offset > 0 and update_id < last_offset:
                continue
            message = update.get("message")
            if not message:
                continue
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            if chat_id is not None:
                handle_result = handle_message(text, chat_id, update_id)
                processed.append({"update_id": update_id, "handled": handle_result, "text": text})
                max_update_id = max(max_update_id, update_id)

        if max_update_id >= last_offset:
            save_offset(max_update_id + 1)

        return {"statusCode": 200, "body": {"processed_count": len(processed), "messages": processed}}
    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "body": str(e)}

# -------------------- Run locally --------------------
if __name__ == "__main__":
    while True:
        lambda_handler()
        time.sleep(5)

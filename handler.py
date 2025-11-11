import json
import os
import requests
import boto3
import time
from typing import Any, Dict, Optional

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# DynamoDB setup for offset tracking (uses the existing chatbot-sessions table)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('chatbot-sessions')
OFFSET_PK = 0  # Number 0 for global bot state (matches pk type "N")
OFFSET_SK = 'last_update_id'

def get_last_offset() -> int:
    """Fetch the last processed update_id from DynamoDB (default 0 if none)."""
    try:
        response = table.get_item(Key={'pk': OFFSET_PK, 'sk': OFFSET_SK})
        if 'Item' in response:
            return int(response['Item'].get('last_offset', 0))
    except Exception:
        pass
    return 0

def save_offset(update_id: int):
    """Save the new last processed update_id to DynamoDB."""
    try:
        table.put_item(
            Item={
                'pk': OFFSET_PK,
                'sk': OFFSET_SK,
                'last_offset': update_id,
                'last_updated_ts': int(time.time())  # Unix timestamp
            }
        )
    except Exception:
        pass  # Fail silently for demo

def poll_messages(offset: int = 0) -> Dict[str, Any]:
    """Poll Telegram getUpdates with offset to avoid reprocessing."""
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "TELEGRAM_TOKEN not set"}
    try:
        params = {"limit": 5, "timeout": 0}
        if offset > 0:
            params["offset"] = offset
        resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params)
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_message(chat_id: int, text: str) -> Optional[Dict[str, Any]]:
    """Send a message back to Telegram."""
    if not TELEGRAM_TOKEN:
        return None
    payload = {"chat_id": chat_id, "text": text}
    try:
        resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return resp.json()
    except Exception:
        return None

def handle_message(text: str, chat_id: int) -> str:
    """Handle simple commands: /hello, /help, /echo"""
    if not text:
        send_message(chat_id, "No text received.")
        return "no_text"

    # normalize and trim
    text = text.strip()
    if not text:
        send_message(chat_id, "No text received.")
        return "no_text"

    # split into command and payload; support commands with @botusername
    parts = text.split(" ", 1)
    cmd = parts[0].split("@", 1)[0].lower()

    if cmd == "/hello":
        resp = "Hello! 👋 I'm your demo bot."
        send_message(chat_id, resp)
        return "hello"

    if cmd == "/help":
        resp = "Commands:\n/hello - greeting\n/help - this message\n/echo <text> - echo back the text"
        send_message(chat_id, resp)
        return "help"

    if cmd == "/echo":
        payload = parts[1].strip() if len(parts) > 1 else ""
        resp = payload if payload else "Usage: /echo <text>"
        send_message(chat_id, resp)
        return "echo"

    # default fallback
    send_message(chat_id, "Unknown command. Send /help for available commands.")
    return "unknown"
    

def lambda_handler(event, context):
    """Main Lambda handler. Process all pending messages from Telegram."""
    try:
        last_offset = get_last_offset()
        result = poll_messages(last_offset)
        
        if not result.get("ok"):
            return {"statusCode": 400, "body": f"Telegram API error: {result.get('error', result)}"}
        
        updates = result.get("result", [])
        
        if not updates:
            return {"statusCode": 200, "body": "No messages"}

        # Process all messages (not just the last one)
        processed = []
        max_update_id = last_offset  # Track the highest ID to save
        for update in updates:
            message = update.get("message")
            if not message:
                continue
            
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            update_id = update.get("update_id", 0)
            
            if chat_id is not None:
                handle_result = handle_message(text, chat_id)
                processed.append({
                    "update_id": update_id,
                    "handled": handle_result,
                    "text": text
                })
                max_update_id = max(max_update_id, update_id)
        
        # Acknowledge by saving the next offset (last ID + 1)
        if max_update_id > last_offset:
            save_offset(max_update_id + 1)
        
        return {"statusCode": 200, "body": {"processed_count": len(processed), "messages": processed}}
    except Exception as e:
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
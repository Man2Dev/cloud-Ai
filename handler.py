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
    except Exception as e:
        print(f"Error getting offset: {e}")
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
        print(f"Saved offset: {update_id}")
    except Exception as e:
        print(f"Error saving offset: {e}")

def poll_messages(offset: int = 0) -> Dict[str, Any]:
    """Poll Telegram getUpdates with offset to avoid reprocessing."""
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "TELEGRAM_TOKEN not set"}
    try:
        params = {"limit": 5, "timeout": 0}
        if offset > 0:
            params["offset"] = offset
        
        print(f"Polling with offset: {offset}")
        resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=10)
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

def handle_message(text: str, chat_id: int, update_id: int) -> str:
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

    print(f"Processing update_id={update_id}, command={cmd}")

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
        print(f"Starting with last_offset: {last_offset}")
        
        # FIRST RUN INITIALIZATION: Process only the most recent message
        if last_offset == 0:
            print("First run detected - will process only the latest message")
            initial_poll = poll_messages(0)
            if initial_poll.get("ok"):
                all_updates = initial_poll.get("result", [])
                if all_updates:
                    # Process only the LAST (most recent) message
                    latest_update = all_updates[-1]
                    latest_id = latest_update.get("update_id", 0)
                    
                    # Skip all older messages
                    if len(all_updates) > 1:
                        print(f"Skipping {len(all_updates) - 1} old messages")
                    
                    # Process the latest one
                    message = latest_update.get("message")
                    if message:
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "")
                        if chat_id:
                            handle_result = handle_message(text, chat_id, latest_id)
                            save_offset(latest_id + 1)
                            return {
                                "statusCode": 200,
                                "body": {
                                    "first_run": True,
                                    "processed": handle_result,
                                    "text": text,
                                    "skipped_count": len(all_updates) - 1
                                }
                            }
                    
                    # No message to process, just skip all
                    save_offset(latest_id + 1)
                    return {
                        "statusCode": 200,
                        "body": f"First run: Cleared {len(all_updates)} old messages"
                    }
        
        result = poll_messages(last_offset)
        
        if not result.get("ok"):
            error_msg = f"Telegram API error: {result.get('error', result)}"
            print(error_msg)
            return {"statusCode": 400, "body": error_msg}
        
        updates = result.get("result", [])
        
        if not updates:
            print("No new messages")
            return {"statusCode": 200, "body": "No messages"}

        print(f"Received {len(updates)} updates")

        # Process all NEW messages (those we haven't seen yet)
        processed = []
        max_update_id = last_offset
        
        for update in updates:
            update_id = update.get("update_id", 0)
            
            # Skip if we've already processed this update
            # When last_offset > 0, skip anything with update_id < last_offset
            # When last_offset == 0 (first run), process everything but mark as seen
            if last_offset > 0 and update_id < last_offset:
                print(f"Skipping already-processed update_id={update_id}")
                max_update_id = max(max_update_id, update_id)
                continue
            
            message = update.get("message")
            if not message:
                print(f"No message in update_id={update_id}, skipping")
                max_update_id = max(max_update_id, update_id)
                continue
            
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            
            if chat_id is not None:
                handle_result = handle_message(text, chat_id, update_id)
                processed.append({
                    "update_id": update_id,
                    "handled": handle_result,
                    "text": text
                })
                max_update_id = max(max_update_id, update_id)
        
        # CRITICAL: Save offset to acknowledge we've processed these messages
        # This tells Telegram not to send them again
        if max_update_id >= last_offset:
            new_offset = max_update_id + 1
            save_offset(new_offset)
            print(f"Acknowledged up to update_id={max_update_id}, next offset={new_offset}")
        
        return {
            "statusCode": 200, 
            "body": {
                "processed_count": len(processed), 
                "messages": processed,
                "last_offset": last_offset,
                "new_offset": max_update_id + 1
            }
        }
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return {"statusCode": 500, "body": error_msg}

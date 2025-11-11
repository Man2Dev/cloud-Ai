import json
import os
import requests
from typing import Any, Dict, Optional

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def poll_messages() -> Dict[str, Any]:
    """Poll Telegram getUpdates (simple polling for demo)."""
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "TELEGRAM_TOKEN not set"}
    try:
        resp = requests.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 5, "timeout": 0})
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

    parts = text.strip().split(" ", 1)
    cmd = parts[0].lower()

    if cmd == "/hello":
        resp = "Hello! 👋 I'm your demo bot."
        send_message(chat_id, resp)
        return "hello"

    if cmd == "/help":
        resp = "Commands:\n/hello - greeting\n/help - this message\n/echo <text> - echo back the text"
        send_message(chat_id, resp)
        return "help"

    if cmd == "/echo":
        payload = parts[1] if len(parts) > 1 else ""
        resp = payload or "Usage: /echo <text>"
        send_message(chat_id, resp)
        return "echo"

    # default fallback
    send_message(chat_id, "Unknown command. Send /help for available commands.")
    return "unknown"
    

def lambda_handler(event, context):
    """Main Lambda handler."""
    try:
        # Poll for messages
        result = poll_messages()
        
        if not result.get("ok"):
            return {"statusCode": 400, "body": f"Telegram API error: {result.get('error', result)}"}
        
        updates = result.get("result", [])
        
        if not updates:
            return {"statusCode": 200, "body": "No messages"}

        # return the last message
        message = updates[-1].get("message")
        if not message:
            return {"statusCode": 200, "body": "Not a message"}
        
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        
        # Handle the message
        handle_result = handle_message(text, chat_id)
        
        return {"statusCode": 200, "body": {"handled": handle_result, "message": message}}
    except Exception as e:
        return {"statusCode": 500, "body": f"Error: {str(e)}"}

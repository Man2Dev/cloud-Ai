import os
import time
import json
import requests
import boto3

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
lambda_client = boto3.client("lambda", endpoint_url="http://localhost:4566")

def get_updates(offset=None):
    params = {"timeout": 10, "offset": offset}
    try:
        resp = requests.get(f"{BASE_URL}/getUpdates", params=params)
        print(f"DEBUG: Telegram response: {resp.status_code}, {resp.json()}")
        return resp.json()
    except Exception as e:
        print(f"DEBUG: Error getting updates: {e}")
        return {"result": []}

def send_telegram_message(chat_id, text):
    try:
        response = requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
        print(f"DEBUG: Sent message response: {response.status_code}")
        return response
    except Exception as e:
        print(f"DEBUG: Error sending message: {e}")

def main():
    offset = None
    print("DEBUG: Starting polling...")
    while True:
        print("DEBUG: Getting updates...")
        updates = get_updates(offset)
        print(f"DEBUG: Updates received: {updates}")
        
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            print(f"DEBUG: Processing message - ID: {update['update_id']}, Text: {text}, Chat: {chat_id}")
            
            if not chat_id:
                continue

            # Invoke Lambda - print what we're sending
            payload = {"body": json.dumps({"message": message})}
            print(f"DEBUG: Sending to Lambda: {payload}")
            
            try:
                resp = lambda_client.invoke(
                    FunctionName="telegram-bot",
                    Payload=json.dumps(payload).encode()
                )
                print(f"DEBUG: Lambda response: {resp}")

                body = resp["Payload"].read().decode()
                print(f"DEBUG: Lambda response body: {body}")
                
                try:
                    body_json = json.loads(body)
                    text_response = body_json.get("body", "No response")
                except:
                    text_response = str(body)
                
                print(f"DEBUG: Sending back to Telegram: {text_response}")
                send_telegram_message(chat_id, text_response)
            except Exception as e:
                print(f"DEBUG: Error invoking Lambda: {e}")
                
        time.sleep(2)

if __name__ == "__main__":
    main()

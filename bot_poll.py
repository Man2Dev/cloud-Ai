import os
import time
import json
import requests
import boto3

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def get_updates(offset=None):
    params = {"timeout": 10, "offset": offset}
    try:
        resp = requests.get(f"{BASE_URL}/getUpdates", params=params)
        print(f"Response: {resp.status_code}, {resp.json()}")
        return resp.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return {"result": []}

def send_telegram_message(chat_id, text):
    try:
        response = requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
        print(f"Message sent: {response.status_code}")
        return response
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    # Initialize Lambda client
    lambda_client = boto3.client("lambda", 
        endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1"
    )
    
    offset = None
    print("Starting Telegram bot polling...")
    
    while True:
        try:
            updates = get_updates(offset)
            print(f"Got {len(updates.get('result', []))} updates")
            
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                
                print(f"Processing: {text} from {chat_id}")
                
                if not chat_id:
                    continue

                # Invoke Lambda
                payload = {"body": json.dumps({"message": message})}
                print(f"Invoking Lambda with: {payload}")
                
                try:
                    resp = lambda_client.invoke(
                        FunctionName="telegram-bot",
                        Payload=json.dumps(payload).encode()
                    )

                    body = resp["Payload"].read().decode()
                    print(f"Lambda response: {body}")
                    
                    try:
                        body_json = json.loads(body)
                        text_response = body_json.get("body", "No response")
                    except:
                        text_response = str(body)
                    
                    print(f"Sending back: {text_response}")
                    send_telegram_message(chat_id, text_response)
                    
                except Exception as e:
                    print(f"Error invoking Lambda: {e}")
                    
        except Exception as e:
            print(f"Error in main loop: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()

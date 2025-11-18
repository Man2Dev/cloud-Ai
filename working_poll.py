import os
import time
import json
import requests
import boto3

# Use the token from environment
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8237559983:AAGfZCjYnz1XooqFYuSfJBYK8mJuyXOOH8k")

if not TOKEN or TOKEN == "8237559983:AAGfZCjYnz1XooqFYuSfJBYK8mJuyXOOH8k":
    print("WARNING: Using default token. Set TELEGRAM_TOKEN environment variable for production.")

# Use LocalStack endpoint for Lambda
lambda_client = boto3.client("lambda", 
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1"
)

def get_updates(offset=None):
    """Get updates from Telegram API"""
    base_url = f"https://api.telegram.org/bot{TOKEN}"
    params = {"timeout": 10, "offset": offset}
    try:
        resp = requests.get(f"{base_url}/getUpdates", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Error getting updates: {resp.status_code}, {resp.text}")
            return {"result": []}
    except Exception as e:
        print(f"Exception getting updates: {e}")
        return {"result": []}

def send_telegram_message(chat_id, text):
    """Send message back to Telegram"""
    base_url = f"https://api.telegram.org/bot{TOKEN}"
    try:
        response = requests.post(f"{base_url}/sendMessage", 
                               json={"chat_id": chat_id, "text": text}, 
                               timeout=10)
        if response.status_code != 200:
            print(f"Error sending message: {response.status_code}, {response.text}")
        return response
    except Exception as e:
        print(f"Exception sending message: {e}")

def main():
    """Main polling loop"""
    offset = None
    print("Starting Telegram bot polling...")
    
    while True:
        try:
            updates = get_updates(offset)
            
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                
                if not chat_id:
                    continue
                
                print(f"Received: {text} from chat {chat_id}")
                
                # Prepare payload for Lambda
                payload = {"body": json.dumps({"message": message})}
                
                try:
                    # Invoke Lambda function
                    response = lambda_client.invoke(
                        FunctionName="telegram-bot",
                        Payload=json.dumps(payload)
                    )
                    
                    # Get response from Lambda
                    response_payload = response['Payload'].read().decode('utf-8')
                    lambda_response = json.loads(response_payload)
                    
                    # Extract the bot response text
                    bot_response = lambda_response.get("body", "No response from bot")
                    
                    # Send response back to Telegram
                    send_telegram_message(chat_id, str(bot_response))
                    print(f"Sent response: {bot_response}")
                    
                except Exception as e:
                    error_msg = f"Error processing message: {str(e)}"
                    print(error_msg)
                    send_telegram_message(chat_id, error_msg)
                    
        except Exception as e:
            print(f"Error in main loop: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()

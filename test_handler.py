# test_handler.py
import os
import sys
import json
import boto3
from datetime import datetime

# Add current dir to path so we can import handler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required env var (mimics Terraform)
os.environ["TELEGRAM_TOKEN"] = "fake_token_for_testing"

# Configure DynamoDB for LocalStack (host mode)
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
users_table = dynamodb.Table("chatbot-users")

def mock_download_telegram_file(file_id, token):
    """Mock file download for local testing"""
    return b"Mock file content"

# Patch the handler's download function (if it exists)
try:
    import handler
    if hasattr(handler, 'download_telegram_file'):
        handler.download_telegram_file = mock_download_telegram_file
except ImportError as e:
    print(f"❌ Failed to import handler.py: {e}")
    sys.exit(1)

def test_save_command():
    """Test /save key value command"""
    print("🧪 Testing /save command...")
    
    # Simulate Telegram webhook event
    test_event = {
        "body": json.dumps({
            "update_id": 10060,
            "message": {
                "message_id": 700,
                "from": {"id": 111222333, "is_bot": False, "first_name": "Tester"},
                "chat": {"id": 111222333, "type": "private"},
                "date": int(datetime.now().timestamp()),
                "text": "/save language Python"
            }
        })
    }

    # Call your Lambda handler
    try:
        result = handler.lambda_handler(test_event, {})
        print(f"✅ Lambda Response: {result}")
    except Exception as e:
        print(f"❌ Lambda Error: {e}")
        return

    # Verify in DynamoDB
    try:
        resp = users_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(111222333)
        )
        items = resp.get("Items", [])
        if items:
            saved = next((item for item in items if item["sk"] == "language"), None)
            if saved and saved["value"] == "Python":
                print("✅ DynamoDB: Correct value saved!")
            else:
                print(f"⚠️ DynamoDB: Unexpected data: {items}")
        else:
            print("❌ DynamoDB: No items found")
    except Exception as e:
        print(f"❌ DynamoDB Error: {e}")

def test_photo_upload():
    """Test photo upload to S3"""
    print("\n🧪 Testing photo upload...")
    
    # Configure S3
    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    test_event = {
        "body": json.dumps({
            "update_id": 10061,
            "message": {
                "message_id": 701,
                "from": {"id": 111222333, "is_bot": False, "first_name": "Tester"},
                "chat": {"id": 111222333, "type": "private"},
                "date": int(datetime.now().timestamp()),
                "photo": [{"file_id": "AgAC_mock123", "file_unique_id": "AQAD123"}]
            }
        })
    }

    try:
        result = handler.lambda_handler(test_event, {})
        print(f"✅ Lambda Response: {result}")
    except Exception as e:
        print(f"❌ Lambda Error: {e}")
        return

    # Verify in S3
    try:
        response = s3.list_objects_v2(Bucket="chatbot-conversations", Prefix="111222333/")
        if "Contents" in response:
            photo_key = response["Contents"][0]["Key"]
            print(f"✅ S3: File saved as {photo_key}")
            
            # Get file content
            obj = s3.get_object(Bucket="chatbot-conversations", Key=photo_key)
            content = obj["Body"].read()
            if content == b"Mock file content":
                print("✅ S3: Correct content saved!")
            else:
                print(f"⚠️ S3: Unexpected content: {content}")
        else:
            print("❌ S3: No files found")
    except Exception as e:
        print(f"❌ S3 Error: {e}")

if __name__ == "__main__":
    print("🚀 Local Lambda Test Suite")
    print("-" * 30)
    
    # Test text commands
    test_save_command()
    
    # Test file uploads
    test_photo_upload()
    
    print("\n✅ All tests completed!")
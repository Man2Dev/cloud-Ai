#!/usr/bin/python
"""
LocalStack AI Chatbot Infrastructure Demo
Demonstrates S3 and DynamoDB operations for the chatbot system
"""

import boto3
import json
import uuid
import time
from datetime import datetime
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure boto3 to use LocalStack
def get_localstack_client(service_name):
    """Create a boto3 client configured for LocalStack"""
    return boto3.client(
        service_name,
        endpoint_url='http://localhost:4566',
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )

# Initialize clients
s3_client = get_localstack_client('s3')
dynamodb_client = get_localstack_client('dynamodb')
dynamodb_resource = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:4566',
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1'
)

# Configuration
BUCKET_NAME = 'chatbot-conversations'
TABLE_NAME = 'chatbot-sessions'

def verify_s3_bucket():
    """Verify S3 bucket exists and is accessible"""
    print("\n" + "="*60)
    print("🪣 TESTING S3 BUCKET")
    print("="*60)
    
    try:
        # List all buckets
        response = s3_client.list_buckets()
        print(f"✓ Found {len(response['Buckets'])} bucket(s):")
        for bucket in response['Buckets']:
            print(f"  - {bucket['Name']}")
        
        # Verify our bucket exists
        if BUCKET_NAME in [b['Name'] for b in response['Buckets']]:
            print(f"\n✓ Target bucket '{BUCKET_NAME}' exists!")
            return True
        else:
            print(f"\n✗ Bucket '{BUCKET_NAME}' not found!")
            return False
    except ClientError as e:
        print(f"✗ Error accessing S3: {e}")
        return False

def test_s3_operations():
    """Test S3 upload and download operations"""
    print("\n" + "="*60)
    print("📤 TESTING S3 OPERATIONS")
    print("="*60)
    
    # Create sample conversation data
    user_id = 12345678  # Numeric user ID
    model_name = "llama3"
    session_id = str(uuid.uuid4())
    
    conversation_data = {
        "user_id": user_id,
        "model": model_name,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Hello! How are you?"},
            {"role": "assistant", "content": "I'm doing great! How can I help you today?"},
            {"role": "user", "content": "Tell me about Python."},
            {"role": "assistant", "content": "Python is a versatile programming language..."}
        ],
        "metadata": {
            "temperature": "0.7",  # Store as string in S3 JSON
            "max_tokens": 2000,
            "ollama_endpoint": "http://localhost:11434"
        }
    }
    
    # Upload to S3
    s3_key = f"{user_id}/model_{model_name}/{session_id}.json"
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(conversation_data, indent=2),
            ContentType='application/json'
        )
        print(f"✓ Uploaded conversation to: s3://{BUCKET_NAME}/{s3_key}")
        
        # List objects in bucket
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        if 'Contents' in response:
            print(f"\n✓ Files in bucket:")
            for obj in response['Contents']:
                print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        
        # Download and verify
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        downloaded_data = json.loads(response['Body'].read())
        print(f"\n✓ Downloaded and verified conversation data")
        print(f"  - Session: {downloaded_data['session_id']}")
        print(f"  - Messages: {len(downloaded_data['messages'])}")
        
        return s3_key
    except ClientError as e:
        print(f"✗ Error with S3 operations: {e}")
        return None

def verify_dynamodb_table():
    """Verify DynamoDB table exists and check its structure"""
    print("\n" + "="*60)
    print("🗄️  TESTING DYNAMODB TABLE")
    print("="*60)
    
    try:
        # List tables
        response = dynamodb_client.list_tables()
        print(f"✓ Found {len(response['TableNames'])} table(s):")
        for table_name in response['TableNames']:
            print(f"  - {table_name}")
        
        # Describe our table
        if TABLE_NAME in response['TableNames']:
            print(f"\n✓ Target table '{TABLE_NAME}' exists!")
            
            table_info = dynamodb_client.describe_table(TableName=TABLE_NAME)
            table_desc = table_info['Table']
            
            print(f"\nTable Details:")
            print(f"  - Status: {table_desc['TableStatus']}")
            print(f"  - Item Count: {table_desc['ItemCount']}")
            print(f"  - Keys:")
            for key in table_desc['KeySchema']:
                attr_type = next(a['AttributeType'] for a in table_desc['AttributeDefinitions'] 
                               if a['AttributeName'] == key['AttributeName'])
                print(f"    • {key['AttributeName']} ({key['KeyType']}) - Type: {attr_type}")
            
            if 'GlobalSecondaryIndexes' in table_desc:
                print(f"  - Global Secondary Indexes:")
                for gsi in table_desc['GlobalSecondaryIndexes']:
                    print(f"    • {gsi['IndexName']}")
                    for key in gsi['KeySchema']:
                        print(f"      - {key['AttributeName']} ({key['KeyType']})")
            
            if 'TimeToLiveDescription' in table_desc:
                ttl = table_desc['TimeToLiveDescription']
                if ttl['TimeToLiveStatus'] == 'ENABLED':
                    print(f"  - TTL: Enabled on '{ttl.get('AttributeName', 'N/A')}'")
            
            return True
        else:
            print(f"\n✗ Table '{TABLE_NAME}' not found!")
            return False
    except ClientError as e:
        print(f"✗ Error accessing DynamoDB: {e}")
        return False

def test_dynamodb_operations(s3_path=None):
    """Test DynamoDB CRUD operations"""
    print("\n" + "="*60)
    print("💾 TESTING DYNAMODB OPERATIONS")
    print("="*60)
    
    table = dynamodb_resource.Table(TABLE_NAME)
    
    # Sample session data - pk is now a Number (user_id)
    user_id = 12345678  # Numeric user ID
    model_name = "llama3"
    session_id = str(uuid.uuid4())
    current_timestamp = int(time.time())
    
    # 1. PUT ITEM - Create a new session
    print("\n1️⃣ Creating new session...")
    try:
        item = {
            'pk': user_id,  # Number type
            'sk': session_id,  # UUID string
            'model_name': model_name,
            'session_id': session_id,
            'user_id': str(user_id),
            'chat_id': '987654321',
            'is_active': 1,  # 1 = active, 0 = archived
            'conversation': json.dumps([
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"}
            ]),
            'last_message_ts': current_timestamp,
            'created_at': datetime.now().isoformat(),
            'ollama_endpoint': 'http://localhost:11434',
            'temperature': Decimal('0.7'),  # Use Decimal for float values
            'max_tokens': 2000,
            's3_path': s3_path or '',
            'ttl': current_timestamp + (30 * 24 * 60 * 60)  # Expire in 30 days
        }
        
        table.put_item(Item=item)
        print(f"✓ Created session: {session_id}")
        print(f"  - PK (user_id): {item['pk']}")
        print(f"  - SK (session_id): {item['sk']}")
        print(f"  - Model: {item['model_name']}")
        print(f"  - Active: {item['is_active']}")
    except ClientError as e:
        print(f"✗ Error creating session: {e}")
        return
    
    # 2. GET ITEM - Retrieve the session
    print("\n2️⃣ Retrieving session...")
    try:
        response = table.get_item(
            Key={
                'pk': user_id,
                'sk': session_id
            }
        )
        if 'Item' in response:
            print(f"✓ Retrieved session successfully")
            print(f"  - Model: {response['Item']['model_name']}")
            print(f"  - Active: {response['Item']['is_active']}")
            print(f"  - Last message timestamp: {response['Item']['last_message_ts']}")
            if 's3_path' in response['Item'] and response['Item']['s3_path']:
                print(f"  - S3 Path: {response['Item']['s3_path']}")
        else:
            print("✗ Session not found")
    except ClientError as e:
        print(f"✗ Error retrieving session: {e}")
    
    # 3. QUERY - Get all sessions for a user
    print("\n3️⃣ Querying all sessions for user...")
    try:
        response = table.query(
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={
                ':pk': user_id
            }
        )
        print(f"✓ Found {response['Count']} session(s) for user {user_id}")
        for item in response['Items']:
            active_status = "Active" if item['is_active'] == 1 else "Archived"
            print(f"  - Session: {item['sk'][:8]}... (Model: {item['model_name']}, Status: {active_status})")
    except ClientError as e:
        print(f"✗ Error querying sessions: {e}")
    
    # 4. UPDATE ITEM - Update session status to archived
    print("\n4️⃣ Updating session status...")
    try:
        table.update_item(
            Key={
                'pk': user_id,
                'sk': session_id
            },
            UpdateExpression='SET is_active = :is_active, last_message_ts = :ts',
            ExpressionAttributeValues={
                ':is_active': 0,  # Archive the session
                ':ts': int(time.time())
            }
        )
        print(f"✓ Updated session status to 'archived' (is_active = 0)")
    except ClientError as e:
        print(f"✗ Error updating session: {e}")
    
    # 5. QUERY GSI - Query by model name across all users
    print("\n5️⃣ Querying Global Secondary Index (model_index)...")
    try:
        response = table.query(
            IndexName='model_index',
            KeyConditionExpression='model_name = :model',
            ExpressionAttributeValues={
                ':model': model_name
            }
        )
        print(f"✓ Found {response['Count']} session(s) using model '{model_name}'")
        for item in response['Items']:
            print(f"  - User: {item['pk']}, Session: {item['sk'][:8]}...")
    except ClientError as e:
        print(f"✗ Error querying GSI (model_index): {e}")
    
    # 6. QUERY GSI - Query active sessions across all users
    print("\n6️⃣ Querying Global Secondary Index (active_sessions_index)...")
    try:
        # Query for active sessions (is_active = 1)
        response = table.query(
            IndexName='active_sessions_index',
            KeyConditionExpression='is_active = :is_active',
            ExpressionAttributeValues={
                ':is_active': 1
            },
            ScanIndexForward=False,  # Sort by last_message_ts descending
            Limit=10
        )
        print(f"✓ Found {response['Count']} active session(s)")
        for item in response['Items']:
            # Convert Decimal to int for datetime
            timestamp = datetime.fromtimestamp(int(item['last_message_ts'])).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - User: {item['pk']}, Model: {item['model_name']}, Last message: {timestamp}")
    except ClientError as e:
        print(f"✗ Error querying GSI (active_sessions_index): {e}")
    
    # 7. SCAN - Get all items (for demo purposes)
    print("\n7️⃣ Scanning entire table...")
    try:
        response = table.scan()
        print(f"✓ Total items in table: {response['Count']}")
        
        # Count active vs archived
        active_count = sum(1 for item in response['Items'] if item.get('is_active', 0) == 1)
        archived_count = response['Count'] - active_count
        print(f"  - Active sessions: {active_count}")
        print(f"  - Archived sessions: {archived_count}")
    except ClientError as e:
        print(f"✗ Error scanning table: {e}")

def cleanup_demo_data():
    """Optional: Clean up demo data"""
    print("\n" + "="*60)
    print("🧹 CLEANUP (Optional)")
    print("="*60)
    
    choice = input("\nDo you want to clean up demo data? (y/n): ").lower()
    if choice != 'y':
        print("Skipping cleanup.")
        return
    
    # Clean S3
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                print(f"✓ Deleted S3 object: {obj['Key']}")
        else:
            print("✓ No S3 objects to delete")
    except ClientError as e:
        print(f"✗ Error cleaning S3: {e}")
    
    # Clean DynamoDB
    try:
        table = dynamodb_resource.Table(TABLE_NAME)
        response = table.scan()
        if response['Items']:
            for item in response['Items']:
                table.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
                print(f"✓ Deleted DynamoDB item: PK={item['pk']}, SK={item['sk'][:8]}...")
        else:
            print("✓ No DynamoDB items to delete")
    except ClientError as e:
        print(f"✗ Error cleaning DynamoDB: {e}")
    
    print("\n✓ Cleanup complete!")

def main():
    """Main demo function"""
    print("\n" + "="*60)
    print("🚀 LOCALSTACK AI CHATBOT INFRASTRUCTURE DEMO")
    print("="*60)
    print("\nThis script will demonstrate:")
    print("  • S3 bucket operations (upload/download)")
    print("  • DynamoDB CRUD operations")
    print("  • Global Secondary Index queries (model_index, active_sessions_index)")
    print("  • TTL configuration")
    print("\nMake sure LocalStack is running: docker compose up -d")
    print("="*60)
    
    input("\nPress Enter to start the demo...")
    
    # Run tests
    s3_exists = verify_s3_bucket()
    if not s3_exists:
        print("\n⚠️  S3 bucket not found. Run 'terraform apply' first!")
        return
    
    s3_path = test_s3_operations()
    
    dynamodb_exists = verify_dynamodb_table()
    if not dynamodb_exists:
        print("\n⚠️  DynamoDB table not found. Run 'terraform apply' first!")
        return
    
    test_dynamodb_operations(s3_path)
    
    cleanup_demo_data()
    
    print("\n" + "="*60)
    print("✅ DEMO COMPLETE!")
    print("="*60)
    print("\nYour LocalStack infrastructure is working correctly!")
    print("You can now use these resources for your AI chatbot.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
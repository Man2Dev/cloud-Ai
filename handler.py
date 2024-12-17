import json
import os
import requests
import boto3
import time
import uuid
from typing import Any, Dict, Optional, List
from datetime import datetime

from boto3.dynamodb.conditions import Key

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")

# DynamoDB setup - use environment variable for region if set
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('chatbot-sessions')
OFFSET_PK = 0
OFFSET_SK = 'last_update_id'

# S3 setup - bucket name can come from environment variable
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'chatbot-conversations')
s3_client = boto3.client('s3')
ARCHIVE_BUCKET = S3_BUCKET_NAME
ARCHIVE_PREFIX = 'archives'


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
                'last_updated_ts': int(time.time())
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


def send_document(chat_id: int, file_content: bytes, filename: str, caption: str = "") -> Optional[Dict[str, Any]]:
    """Send a document/file to Telegram chat."""
    if not TELEGRAM_TOKEN:
        return None
    try:
        files = {'document': (filename, file_content, 'application/json')}
        data = {'chat_id': chat_id}
        if caption:
            data['caption'] = caption
        resp = requests.post(f"{TELEGRAM_API}/sendDocument", data=data, files=files, timeout=30)
        return resp.json()
    except Exception as e:
        print(f"Error sending document: {e}")
        return None


def get_telegram_file(file_id: str) -> Optional[bytes]:
    """Download a file from Telegram by file_id."""
    if not TELEGRAM_TOKEN:
        return None
    try:
        resp = requests.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            print(f"Failed to get file info: {data}")
            return None

        file_path = data["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        file_resp = requests.get(download_url, timeout=30)
        if file_resp.status_code == 200:
            return file_resp.content
        else:
            print(f"Failed to download file: {file_resp.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None


def get_user_items(user_id: int) -> List[Dict[str, Any]]:
    """Query all items for a user (sessions)."""
    try:
        response = table.query(
            KeyConditionExpression=Key('pk').eq(user_id)
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying user items for {user_id}: {e}")
        return []


def get_active_session(user_id: int) -> Optional[Dict[str, Any]]:
    """Get the active session for a user."""
    items = get_user_items(user_id)
    for item in items:
        if item.get('is_active', 0) == 1:
            print(f"Found active session for user {user_id}: {item['sk']}")
            return item
    print(f"No active session found for user {user_id}")
    return None


def create_session(user_id: int, model_name: str = "llama3") -> Dict[str, Any]:
    """Create a new session, deactivate old active ones."""
    session_id = str(uuid.uuid4())
    sk = f"MODEL#{model_name}#SESSION#{session_id}"
    now = int(time.time())
    item = {
        'pk': user_id,
        'sk': sk,
        'model_name': model_name,
        'session_id': session_id,
        'is_active': 1,
        'last_message_ts': now,
        'conversation': [],
        'user_id': user_id,
        's3_path': '',
    }
    existing_items = get_user_items(user_id)
    for it in existing_items:
        if it.get('is_active', 0) == 1 and it['sk'] != sk:
            print(f"Deactivating existing session for user {user_id}: {it['sk']}")
            table.update_item(
                Key={'pk': user_id, 'sk': it['sk']},
                UpdateExpression='SET is_active = :val',
                ExpressionAttributeValues={':val': 0}
            )
    table.put_item(Item=item)
    print(f"Created new session for user {user_id}: {sk}")
    return item


def get_current_session(user_id: int) -> Dict[str, Any]:
    """Get active session or create one if none exists."""
    session = get_active_session(user_id)
    if not session:
        print(f"No active session, creating new for user {user_id}")
        session = create_session(user_id)
    else:
        print(f"Using existing active session for user {user_id}")
    return session


def append_to_conversation(session: Dict[str, Any], message_dict: Dict[str, Any]):
    """Append a message to the session's conversation and update timestamp."""
    session['conversation'].append(message_dict)
    session['last_message_ts'] = int(time.time())
    table.put_item(Item=session)
    print(f"Appended message to session {session['sk']}, conversation length: {len(session['conversation'])}")


def call_ollama(model: str, messages: List[Dict[str, Any]]) -> str:
    """Call Ollama API for chat completion."""
    if not OLLAMA_URL:
        print("OLLAMA_URL not configured.")
        return "Ollama URL not configured. Set OLLAMA_URL env var."
    print(f"Calling Ollama at {OLLAMA_URL} with model '{model}' (context length: {len(messages)})")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            response_content = data['message']['content']
            print(f"Ollama success: Response length {len(response_content)} chars")
            return response_content
        else:
            print(f"Ollama API error: {resp.status_code} - {resp.text}")
            return f"Sorry, AI response unavailable (error {resp.status_code}). Use /status to check connection."
    except Exception as e:
        print(f"Ollama call error: {e}")
        return f"Sorry, AI response unavailable (connection error). Use /status to check connection."


# ==================== ARCHIVE FUNCTIONS ====================

def get_archive_s3_key(user_id: int, session_id: str) -> str:
    """Generate S3 key for archived session: archives/{user_id}/{session_id}.json"""
    return f"{ARCHIVE_PREFIX}/{user_id}/{session_id}.json"


def archive_session_to_s3(user_id: int, session: Dict[str, Any]) -> Optional[str]:
    """Archive a session from DynamoDB to S3."""
    session_id = session.get('session_id', '')
    if not session_id:
        print(f"Session missing session_id: {session}")
        return None

    archive_data = {
        'user_id': user_id,
        'session_id': session_id,
        'model_name': session.get('model_name', 'unknown'),
        'conversation': session.get('conversation', []),
        'original_sk': session.get('sk', ''),
        'last_message_ts': session.get('last_message_ts', 0),
        'archived_at': datetime.utcnow().isoformat() + 'Z',
        'archive_version': '1.0'
    }

    s3_key = get_archive_s3_key(user_id, session_id)

    try:
        s3_client.put_object(
            Bucket=ARCHIVE_BUCKET,
            Key=s3_key,
            Body=json.dumps(archive_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'user_id': str(user_id),
                'session_id': session_id,
                'model_name': session.get('model_name', 'unknown')
            }
        )
        print(f"Archived session to S3: s3://{ARCHIVE_BUCKET}/{s3_key}")
        return s3_key
    except Exception as e:
        print(f"Error archiving to S3: {e}")
        return None


def delete_session_from_dynamodb(user_id: int, sk: str) -> bool:
    """Delete a session from DynamoDB after archiving."""
    try:
        table.delete_item(Key={'pk': user_id, 'sk': sk})
        print(f"Deleted session from DynamoDB: pk={user_id}, sk={sk}")
        return True
    except Exception as e:
        print(f"Error deleting session from DynamoDB: {e}")
        return False


def list_user_archives(user_id: int) -> List[Dict[str, Any]]:
    """List all archived sessions for a user from S3."""
    prefix = f"{ARCHIVE_PREFIX}/{user_id}/"
    archives = []

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=ARCHIVE_BUCKET, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                session_id = key.split('/')[-1].replace('.json', '')
                archives.append({
                    'session_id': session_id,
                    's3_key': key,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat() if obj.get('LastModified') else ''
                })
        print(f"Found {len(archives)} archives for user {user_id}")
    except Exception as e:
        print(f"Error listing archives: {e}")

    return archives


def get_archive_from_s3(user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an archived session from S3."""
    s3_key = get_archive_s3_key(user_id, session_id)

    try:
        response = s3_client.get_object(Bucket=ARCHIVE_BUCKET, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        print(f"Archive not found: {s3_key}")
        return None
    except Exception as e:
        print(f"Error retrieving archive: {e}")
        return None


def import_archive_to_s3(user_id: int, archive_data: Dict[str, Any]) -> Optional[str]:
    """Import an archive file to S3 for a user."""
    new_session_id = str(uuid.uuid4())

    imported_data = {
        'user_id': user_id,
        'session_id': new_session_id,
        'model_name': archive_data.get('model_name', 'imported'),
        'conversation': archive_data.get('conversation', []),
        'original_session_id': archive_data.get('session_id', 'unknown'),
        'original_user_id': archive_data.get('user_id', 'unknown'),
        'last_message_ts': archive_data.get('last_message_ts', 0),
        'archived_at': archive_data.get('archived_at', datetime.utcnow().isoformat() + 'Z'),
        'imported_at': datetime.utcnow().isoformat() + 'Z',
        'archive_version': '1.0'
    }

    s3_key = get_archive_s3_key(user_id, new_session_id)

    try:
        s3_client.put_object(
            Bucket=ARCHIVE_BUCKET,
            Key=s3_key,
            Body=json.dumps(imported_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'user_id': str(user_id),
                'session_id': new_session_id,
                'imported': 'true'
            }
        )
        print(f"Imported archive to S3: s3://{ARCHIVE_BUCKET}/{s3_key}")
        return new_session_id
    except Exception as e:
        print(f"Error importing archive to S3: {e}")
        return None


# ==================== COMMAND HANDLERS ====================

def handle_command(cmd: str, payload: str, chat_id: int, user_id: int, update_id: int) -> str:
    """Handle bot commands."""
    print(f"Handling command '{cmd}' for user {user_id} in chat {chat_id}")

    if cmd == "/start" or cmd == "/hello":
        session = get_current_session(user_id)
        resp = f"Hello! Your current model is {session['model_name']}. Chat away or use /help."
        send_message(chat_id, resp)
        return "start_or_hello"

    if cmd == "/help":
        resp = """Commands:
/start or /hello - Greeting and session init
/newsession - Start a new chat session
/listsessions - List your sessions
/switch <number> - Switch to a session (e.g., /switch 1)
/history - Show recent messages in current session
/status - Check system status (Ollama integration coming soon)
/echo <text> - Echo back text

Archive Commands:
/archive - List sessions to archive
/archive <number> - Archive a specific session to S3
/listarchives - List your archived sessions
/export <number> - Export an archive as a file
(Send a JSON file to import an archive)

Note: AI chat is not yet implemented."""
        send_message(chat_id, resp)
        return "help"

    if cmd == "/status":
        resp_msg = "🟢 Bot is running on AWS!\nOllama AI integration not yet implemented. Stay tuned!"
        send_message(chat_id, resp_msg)
        return "status"

    if cmd == "/newsession":
        new_session = create_session(user_id)
        resp = f"New session created with model '{new_session['model_name']}' (ID: {new_session['session_id'][:8]})."
        send_message(chat_id, resp)
        return "newsession"

    if cmd == "/listsessions":
        items = get_user_items(user_id)
        sessions = [it for it in items if it['sk'].startswith('MODEL#')]
        if not sessions:
            send_message(chat_id, "No sessions yet. Start chatting or use /newsession.")
            return "no_sessions"
        msg = "Your sessions:\n"
        for i, session in enumerate(sessions):
            active = " (active)" if session.get('is_active', 0) == 1 else ""
            model = session['model_name']
            sid = session['session_id'][:8]
            ts_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(session.get('last_message_ts', 0)))
            msg_count = len(session.get('conversation', []))
            msg += f"{i+1}. {model} ({sid}){active} - {msg_count} msgs - Last: {ts_str}\n"
        send_message(chat_id, msg)
        return "listsessions"

    if cmd == "/switch":
        try:
            idx = int(payload.strip()) - 1
            items = get_user_items(user_id)
            sessions = [it for it in items if it['sk'].startswith('MODEL#')]
            if 0 <= idx < len(sessions):
                target_sk = sessions[idx]['sk']
                for session in sessions:
                    val = 1 if session['sk'] == target_sk else 0
                    table.update_item(
                        Key={'pk': user_id, 'sk': session['sk']},
                        UpdateExpression='SET is_active = :val',
                        ExpressionAttributeValues={':val': val}
                    )
                model = sessions[idx]['model_name']
                resp = f"Switched to session {idx+1} (model: {model})."
                send_message(chat_id, resp)
                return "switch"
            else:
                send_message(chat_id, "Invalid session number. Use /listsessions.")
                return "invalid_switch"
        except ValueError:
            send_message(chat_id, "Usage: /switch <number> (e.g., /switch 1)")
            return "invalid_switch"

    if cmd == "/history":
        session = get_current_session(user_id)
        conversation = session.get('conversation', [])
        if isinstance(conversation, str):
            try:
                conversation = json.loads(conversation)
            except:
                conversation = []

        conv = conversation[-5:] if conversation else []
        if not conv:
            send_message(chat_id, "No messages in this session yet.")
            return "no_history"
        msg = "Recent conversation:\n"
        for m in conv:
            role = m.get('role', 'unknown').capitalize()
            content = m.get('content', '')
            content = (content[:100] + "...") if len(content) > 100 else content
            ts = m.get('ts', int(time.time()))
            ts_str = time.strftime('%H:%M', time.localtime(ts))
            msg += f"{role} ({ts_str}): {content}\n"
        send_message(chat_id, msg)
        return "history"

    if cmd == "/echo":
        resp = payload.strip() if payload.strip() else "Usage: /echo <text>"
        send_message(chat_id, resp)
        return "echo"

    # ==================== ARCHIVE COMMANDS ====================

    if cmd == "/archive":
        items = get_user_items(user_id)
        sessions = [it for it in items if it['sk'].startswith('MODEL#')]

        if not sessions:
            send_message(chat_id, "No sessions to archive. Start chatting first!")
            return "no_sessions_to_archive"

        if not payload.strip():
            msg = "Sessions available to archive:\n"
            for i, session in enumerate(sessions):
                active = " (active)" if session.get('is_active', 0) == 1 else ""
                model = session['model_name']
                sid = session['session_id'][:8]
                msg_count = len(session.get('conversation', []))
                ts_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(session.get('last_message_ts', 0)))
                msg += f"{i+1}. {model} ({sid}){active} - {msg_count} msgs - {ts_str}\n"
            msg += "\nUse /archive <number> to archive a session (e.g., /archive 1)"
            send_message(chat_id, msg)
            return "list_for_archive"

        try:
            idx = int(payload.strip()) - 1
            if 0 <= idx < len(sessions):
                session = sessions[idx]
                session_id = session['session_id']

                s3_key = archive_session_to_s3(user_id, session)
                if not s3_key:
                    send_message(chat_id, "Failed to archive session to S3. Please try again.")
                    return "archive_s3_error"

                if delete_session_from_dynamodb(user_id, session['sk']):
                    msg_count = len(session.get('conversation', []))
                    resp = f"Session archived successfully!\n"
                    resp += f"- Model: {session['model_name']}\n"
                    resp += f"- Messages: {msg_count}\n"
                    resp += f"- Archive ID: {session_id[:8]}\n"
                    resp += f"\nUse /listarchives to see your archives."
                    send_message(chat_id, resp)
                    return "archived"
                else:
                    send_message(chat_id, "Session saved to S3 but failed to remove from active storage.")
                    return "archive_cleanup_error"
            else:
                send_message(chat_id, "Invalid session number. Use /archive to see available sessions.")
                return "invalid_archive_number"
        except ValueError:
            send_message(chat_id, "Usage: /archive <number> (e.g., /archive 1)")
            return "invalid_archive_format"

    if cmd == "/listarchives":
        archives = list_user_archives(user_id)

        if not archives:
            send_message(chat_id, "No archived sessions yet. Use /archive to archive a session.")
            return "no_archives"

        msg = "Your archived sessions:\n"
        for i, archive in enumerate(archives):
            sid = archive['session_id'][:8]
            size_kb = archive['size'] / 1024
            last_mod = archive.get('last_modified', 'N/A')[:10]
            msg += f"{i+1}. Archive {sid} - {size_kb:.1f}KB - {last_mod}\n"
        msg += "\nUse /export <number> to download an archive."
        send_message(chat_id, msg)
        return "listarchives"

    if cmd == "/export":
        if not payload.strip():
            send_message(chat_id, "Usage: /export <number> (e.g., /export 1)\nUse /listarchives to see available archives.")
            return "export_no_number"

        archives = list_user_archives(user_id)

        if not archives:
            send_message(chat_id, "No archived sessions to export. Use /archive first.")
            return "no_archives_to_export"

        try:
            idx = int(payload.strip()) - 1
            if 0 <= idx < len(archives):
                archive_info = archives[idx]
                session_id = archive_info['session_id']

                archive_data = get_archive_from_s3(user_id, session_id)
                if not archive_data:
                    send_message(chat_id, "Failed to retrieve archive. Please try again.")
                    return "export_retrieve_error"

                filename = f"archive_{session_id[:8]}_{archive_data.get('model_name', 'chat')}.json"
                file_content = json.dumps(archive_data, indent=2, default=str).encode('utf-8')

                msg_count = len(archive_data.get('conversation', []))
                caption = f"Archive: {archive_data.get('model_name', 'unknown')} - {msg_count} messages"

                result = send_document(chat_id, file_content, filename, caption)
                if result and result.get('ok'):
                    send_message(chat_id, "Archive exported! You can send this file back to import it later.")
                    return "exported"
                else:
                    send_message(chat_id, "Failed to send archive file. Please try again.")
                    return "export_send_error"
            else:
                send_message(chat_id, "Invalid archive number. Use /listarchives to see available archives.")
                return "invalid_export_number"
        except ValueError:
            send_message(chat_id, "Usage: /export <number> (e.g., /export 1)")
            return "invalid_export_format"

    send_message(chat_id, "Unknown command. Send /help for available commands.")
    return "unknown"


def handle_document(document: Dict[str, Any], chat_id: int, user_id: int) -> str:
    """Handle incoming document (file) - for archive imports."""
    file_name = document.get('file_name', '')
    file_id = document.get('file_id', '')
    mime_type = document.get('mime_type', '')

    print(f"Received document: {file_name} ({mime_type}) from user {user_id}")

    if not (file_name.endswith('.json') or mime_type == 'application/json'):
        send_message(chat_id, "Please send a JSON file to import an archive.\nExport archives using /export to get the correct format.")
        return "invalid_file_type"

    file_content = get_telegram_file(file_id)
    if not file_content:
        send_message(chat_id, "Failed to download file. Please try again.")
        return "download_error"

    try:
        archive_data = json.loads(file_content.decode('utf-8'))
    except json.JSONDecodeError as e:
        send_message(chat_id, f"Invalid JSON file. Please send a valid archive export.\nError: {str(e)[:100]}")
        return "json_parse_error"

    if 'conversation' not in archive_data:
        send_message(chat_id, "Invalid archive format. Missing 'conversation' field.\nUse /export to get a valid archive format.")
        return "invalid_archive_format"

    new_session_id = import_archive_to_s3(user_id, archive_data)
    if not new_session_id:
        send_message(chat_id, "Failed to import archive. Please try again.")
        return "import_error"

    msg_count = len(archive_data.get('conversation', []))
    original_model = archive_data.get('model_name', 'unknown')

    resp = f"Archive imported successfully!\n"
    resp += f"- Original model: {original_model}\n"
    resp += f"- Messages: {msg_count}\n"
    resp += f"- New archive ID: {new_session_id[:8]}\n"
    resp += f"\nUse /listarchives to see your archives."
    send_message(chat_id, resp)
    return "imported"


def handle_message(text: str, chat_id: int, user_id: int, update_id: int, document: Optional[Dict[str, Any]] = None) -> str:
    """Handle incoming messages: commands, chat, or documents."""

    if document:
        return handle_document(document, chat_id, user_id)

    if not text:
        send_message(chat_id, "No text received.")
        return "no_text"

    text = text.strip()
    if not text:
        send_message(chat_id, "No text received.")
        return "no_text"

    print(f"Processing update_id={update_id}, text='{text}' for user {user_id} in chat {chat_id}")

    if text.startswith('/'):
        parts = text.split(" ", 1)
        cmd = parts[0].split("@", 1)[0].lower()
        payload = parts[1] if len(parts) > 1 else ""
        return handle_command(cmd, payload, chat_id, user_id, update_id)
    else:
        session = get_current_session(user_id)
        now = int(time.time())

        user_msg = {"role": "user", "content": text, "ts": now}
        append_to_conversation(session, user_msg)

        placeholder_response = "AI is not yet implemented. Your message has been saved to the conversation history for testing."
        ass_msg = {"role": "assistant", "content": placeholder_response, "ts": int(time.time())}
        append_to_conversation(session, ass_msg)

        send_message(chat_id, placeholder_response)
        return "ai_not_ready"


def process_telegram_update(update: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single Telegram update (from webhook or polling)."""
    update_id = update.get("update_id", 0)
    message = update.get("message")
    
    if not message:
        print(f"No message in update_id={update_id}, skipping")
        return {"processed": False, "reason": "no_message"}
    
    chat_id = message.get("chat", {}).get("id")
    from_user = message.get('from', {})
    user_id = from_user.get('id', chat_id)
    text = message.get("text", "")
    document = message.get("document")
    
    if chat_id is None:
        print(f"No chat_id in update_id={update_id}, skipping")
        return {"processed": False, "reason": "no_chat_id"}
    
    handle_result = handle_message(text, chat_id, user_id, update_id, document)
    
    return {
        "processed": True,
        "update_id": update_id,
        "handled": handle_result,
        "text": text if text else "(document)",
        "user_id": user_id
    }


def lambda_handler(event, context):
    """
    Main Lambda handler.
    Supports both:
    1. Webhook mode (API Gateway triggers Lambda with Telegram update in body)
    2. Polling mode (Manual invocation to poll Telegram getUpdates)
    """
    print(f"Event received: {json.dumps(event)[:500]}...")
    
    # Check if this is a webhook request from API Gateway
    if 'body' in event:
        # API Gateway webhook mode
        try:
            body = event.get('body', '{}')
            if isinstance(body, str):
                update = json.loads(body)
            else:
                update = body
            
            print(f"Webhook update received: {json.dumps(update)[:500]}...")
            
            result = process_telegram_update(update)
            
            # Always return 200 to Telegram to acknowledge receipt
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": True, "result": result})
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": False, "error": "Invalid JSON"})
            }
        except Exception as e:
            print(f"Webhook error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": False, "error": str(e)})
            }
    
    # Polling mode (manual invocation or scheduled)
    try:
        last_offset = get_last_offset()
        print(f"Polling mode - Starting with last_offset: {last_offset}")

        if last_offset == 0:
            print("First run detected - will process only the latest message")
            initial_poll = poll_messages(0)
            if initial_poll.get("ok"):
                all_updates = initial_poll.get("result", [])
                if all_updates:
                    latest_update = all_updates[-1]
                    latest_id = latest_update.get("update_id", 0)

                    if len(all_updates) > 1:
                        print(f"Skipping {len(all_updates) - 1} old messages")

                    result = process_telegram_update(latest_update)
                    save_offset(latest_id + 1)
                    return {
                        "statusCode": 200,
                        "body": {
                            "mode": "polling",
                            "first_run": True,
                            "result": result,
                            "skipped_count": len(all_updates) - 1
                        }
                    }

                save_offset(latest_id + 1 if all_updates else 1)
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

        processed = []
        max_update_id = last_offset

        for update in updates:
            update_id = update.get("update_id", 0)

            if last_offset > 0 and update_id < last_offset:
                print(f"Skipping already-processed update_id={update_id}")
                max_update_id = max(max_update_id, update_id)
                continue

            result = process_telegram_update(update)
            if result.get("processed"):
                processed.append(result)
            max_update_id = max(max_update_id, update_id)

        if max_update_id >= last_offset:
            new_offset = max_update_id + 1
            save_offset(new_offset)
            print(f"Acknowledged up to update_id={max_update_id}, next offset={new_offset}")

        return {
            "statusCode": 200,
            "body": {
                "mode": "polling",
                "processed_count": len(processed),
                "messages": processed,
                "last_offset": last_offset,
                "new_offset": max_update_id + 1
            }
        }
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "body": error_msg}

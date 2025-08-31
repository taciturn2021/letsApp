from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from flask import current_app
from app.models.message import Message  
from app.models.user import User  
from app.models.file import File  
from app.models.media import Media  
import datetime
import jwt
import logging
import os


DEBUG_MODE = os.environ.get('FLASK_ENV') == 'development'


logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

def validate_token(token):
    """Validate JWT token and return the decoded token or None if invalid"""
    if not token:
        return None
    try:
        decoded_token = decode_token(token)
        return decoded_token
    except Exception:  
        return None

def register_handlers(socketio):
    """Register all Socket.IO event handlers for chat"""
    
    # Connect and disconnect events are handled in events.py
    # Do not add them here to avoid conflicts
    
    @socketio.on('join')
    def handle_join(data):
        """Handle a user joining a chat room."""
        print("\n========== WEBSOCKET: JOIN REQUEST ==========")
        print(f"Data received: {data}")
        
        token = data.get('token')
        decoded_token = validate_token(token)
        
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            
           
            if DEBUG_MODE:
                print("DEBUG MODE: Allowing connection without token for testing")
                
                test_user_id = "test_user_123"
                room = f"{min(test_user_id, data['recipient'])}_{max(test_user_id, data['recipient'])}"
                join_room(room)
                print(f"DEBUG MODE: User {test_user_id} joined room {room}")
                emit('status', {'message': f'User joined room {room}'}, room=room)
                return
            
            emit('error', {'message': 'Invalid or missing token'})
            return

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        join_room(room)
        print(f"SUCCESS: User {decoded_token['sub']} joined room {room}")
        emit('status', {'message': f'User joined room {room}'}, room=room)

    @socketio.on('leave')
    def handle_leave(data):
        """Handle a user leaving a chat room."""
        print("\n========== WEBSOCKET: LEAVE REQUEST ==========")
        print(f"Data received: {data}")
        
        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            emit('error', {'message': 'Invalid or missing token'})
            return

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        leave_room(room)
        print(f"SUCCESS: User {decoded_token['sub']} left room {room}")
        emit('status', {'message': f'User left room {room}'}, room=room)

    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle sending a message."""
        print("\n========== WEBSOCKET: NEW MESSAGE RECEIVED ==========")
        print(f"Raw message data from client: {data}") 
        
        client_attachment_payload = data.get('attachment')
        if client_attachment_payload:
            print(f"Client attachment payload received: {client_attachment_payload}")
            print(f"Keys in client_attachment_payload: {list(client_attachment_payload.keys()) if isinstance(client_attachment_payload, dict) else 'Not a dict'}")

        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            emit('error', {'message': 'Invalid or missing token'})
            return

        print(f"Token validated for user: {decoded_token['sub']}")

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        print(f"Message room: {room}")
        
        sender_id = decoded_token['sub']
        recipient_id = data['recipient']
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')
        
        attachment_to_save = None # Renamed from 'attachment' to avoid confusion
        
        if client_attachment_payload and isinstance(client_attachment_payload, dict):
           
            media_doc_id = client_attachment_payload.get('fileId') 
            
        
            if not media_doc_id:
                media_doc_id = client_attachment_payload.get('file_id')

            original_filename = client_attachment_payload.get('filename')
            
            resolved_file_type = client_attachment_payload.get('type') or client_attachment_payload.get('file_type') or 'document' 

            print(f"Processing client attachment: media_doc_id='{media_doc_id}', filename='{original_filename}', type='{resolved_file_type}'")

            file_info = None
            if media_doc_id and media_doc_id not in ['undefined', 'null', None, '']:
                print(f"Attempting to fetch Media/File object using ID: {media_doc_id} (type hint: {resolved_file_type})")
                if resolved_file_type in ('image', 'video', 'audio'):
                    file_info = Media.get_by_id(media_doc_id)
                else:
                    file_info = File.get_by_id(media_doc_id)
                
                if file_info:
                    print(f"Successfully fetched by ID: {file_info['_id']}")
                else:
                    # If ID lookup fails, maybe it was a filename passed as fileId by mistake, or bad ID
                    print(f"WARN: Could not find Media/File for ID: {media_doc_id}. Will try filename lookup if available.")
            
            # If file_info not found by ID, AND we have an original_filename, try by filename
            if not file_info and original_filename:
                print(f"Attempting to fetch by filename: '{original_filename}' for user '{sender_id}' (type hint: {resolved_file_type})")
                if resolved_file_type in ('image', 'video', 'audio'):
                    file_info = Media.get_most_recent_by_user_and_filename(sender_id, original_filename)
                else:
                    file_info = File.get_most_recent_by_user_and_filename(sender_id, original_filename)
                
                if file_info:
                    print(f"Successfully fetched by filename: {file_info['_id']}")
                else:
                    print(f"WARN: Could not find Media/File by filename: {original_filename}")

            if file_info:
                # Determine the most reliable message_type from the retrieved file_info
                message_type = file_info.get('media_type') or file_info.get('file_type') or resolved_file_type
                attachment_to_save = {
                    "file_id": str(file_info['_id']),
                    "file_type": message_type,
                    "filename": file_info.get('original_filename', original_filename or ''),
                    "mime_type": file_info.get('mime_type', ''),
                    "size": file_info.get('file_size', 0)
                }
            else:
                print(f"ERROR: Attachment processing failed. No file_info found for: {client_attachment_payload}")
                # Keep original message_type if attachment fails, or reset if it was file-specific
                if message_type not in ['text'] and not content: # If it was e.g. 'video' but no content and attach failed
                    message_type = 'text' # Default to text if attachment fails and no content
        
        print(f"Final attachment to save in DB: {attachment_to_save}")
        print(f"Final message_type for DB: {message_type}")

        try:
            print(f"Creating message in database...")
            message = Message.create(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content=content,
                message_type=message_type,
                attachment=attachment_to_save # Use the processed attachment_to_save
            )
            print(f"Message created successfully with ID: {message['_id']}")
        except Exception as e:
            print(f"ERROR: Failed to save message to database - {str(e)}")
            emit('error', {'message': 'Failed to save message'})
            return

        try:
            # Fetch sender details from User model
            sender = User.get_by_id(sender_id)
            
            # Convert ObjectId and datetime objects to strings
            message_payload = {
                'id': str(message['_id']),
                'sender': str(message['sender_id']),
                'sender_name': sender.get('username', ''),  # Use username as sender_name
                'sender_avatar': sender.get('profile_picture', ''),  # Use profile_picture as sender_avatar
                'recipient': str(message['recipient_id']),
                'content': message['content'],
                'timestamp': message['created_at'].isoformat(),
                'status': message['status'],
                'message_type': message['message_type'],
                'attachment': message['attachment']
            }
            print(f"Broadcasting message to room {room}")
            emit('receive_message', message_payload, room=room)
            print(f"Message broadcast successful")
        except Exception as e:
            print(f"ERROR: Failed to broadcast message - {str(e)}")
            # Optionally notify sender of emission failure
            pass
        
        # Return acknowledgment to the sender
        ack_payload = {
            'status': 'success',
            'message_id': str(message['_id']),
            'timestamp': message['created_at'].isoformat()
        }
        print(f"Sending acknowledgment to sender: {ack_payload}")
        print("========== MESSAGE PROCESSING COMPLETE ==========\n")
        return ack_payload


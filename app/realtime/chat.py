from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from flask import current_app
from app.models.message import Message  # Import the Message model
from app.models.user import User  # Add User model import
from app.models.file import File  # Add File model import
from app.models.media import Media  # Add Media model import
import datetime
import jwt
import logging
import os

# Debug mode for development - set to False in production
DEBUG_MODE = os.environ.get('FLASK_ENV') == 'development'

# Set up logging
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

def validate_token(token):
    """Validate JWT token and return the decoded token or None if invalid"""
    if not token:
        return None
    try:
        decoded_token = decode_token(token)
        return decoded_token
    except Exception:  # Use a generic exception instead of the specific JWTDecodeError
        return None

def register_handlers(socketio):
    """Register all Socket.IO event handlers for chat"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print("\n========== WEBSOCKET: Client Connected ==========")
        
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print("\n========== WEBSOCKET: Client Disconnected ==========")
    
    @socketio.on('join')
    def handle_join(data):
        """Handle a user joining a chat room."""
        print("\n========== WEBSOCKET: JOIN REQUEST ==========")
        print(f"Data received: {data}")
        
        token = data.get('token')
        decoded_token = validate_token(token)
        
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            
            # For debugging - allow connections without tokens in dev mode
            if DEBUG_MODE:
                print("DEBUG MODE: Allowing connection without token for testing")
                # Use a fake user ID for testing
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
        print(f"Message data: {data}")
        
        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            emit('error', {'message': 'Invalid or missing token'})
            return

        print(f"Token validated for user: {decoded_token['sub']}")

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        print(f"Message room: {room}")
        
        sender_id = decoded_token['sub']  # Use the user ID from the token
        recipient_id = data['recipient']
        content = data.get('content', '')
        
        # Get message_type (default to "text")
        message_type = data.get('message_type', 'text')
        
        # Handle different ways the attachment might be provided
        attachment = None
        
        # Case 1: Direct attachment object in the message
        if data.get('attachment'):
            attachment_data = data.get('attachment')
            print(f"Message contains attachment object: {attachment_data}")
            
            # If attachment has file_id, use it directly
            if attachment_data.get('file_id'):
                attachment = attachment_data
            # If attachment only has filename but no file_id, we need to find the file
            elif attachment_data.get('filename'):
                filename = attachment_data.get('filename')
                attachment_type = attachment_data.get('type', 'document')
                
                print(f"Looking for recently uploaded file matching: {filename}")
                
                # Find the most recent file uploaded by this user with the matching filename
                file_info = None
                if attachment_type in ('image', 'video', 'audio'):
                    file_info = Media.get_most_recent_by_user_and_filename(sender_id, filename)
                else:
                    file_info = File.get_most_recent_by_user_and_filename(sender_id, filename)
                
                if file_info:
                    print(f"Found matching file with ID: {file_info['_id']}")
                    attachment = {
                        "file_id": str(file_info['_id']),
                        "file_type": attachment_type,
                        "filename": file_info.get('original_filename', filename),
                        "mime_type": file_info.get('mime_type', ''),
                        "size": file_info.get('file_size', 0)
                    }
                    # Use the file's type for message_type if it was provided
                    if attachment_type:
                        message_type = attachment_type
                else:
                    print(f"WARNING: Could not find recently uploaded file matching '{filename}'")
        
        # Case 2: file_id and file_type directly in the message
        elif data.get('file_id'):
            file_id = data.get('file_id')
            file_type = data.get('file_type', 'document')
            print(f"Message contains direct file reference: {file_id}")
            
            attachment = {
                "file_id": file_id,
                "file_type": file_type
            }
            message_type = file_type
        
        # Case 3: attachments array
        elif data.get('attachments') and len(data.get('attachments')) > 0:
            first_attachment = data.get('attachments')[0]
            print(f"Message contains attachments array: {data.get('attachments')}")
            
            if first_attachment.get('id') and not first_attachment.get('id').startswith('uploading-'):
                attachment = {
                    "file_id": first_attachment.get('id'),
                    "file_type": first_attachment.get('type', 'document'),
                    "filename": first_attachment.get('filename', '')
                }
                message_type = first_attachment.get('type', 'document')
            elif first_attachment.get('filename'):
                # Handle temporary ID case by finding the file based on filename
                filename = first_attachment.get('filename')
                attachment_type = first_attachment.get('type', 'document')
                
                # Try to find recently uploaded file with matching name
                file_info = None
                if attachment_type in ('image', 'video', 'audio'):
                    file_info = Media.get_most_recent_by_user_and_filename(sender_id, filename)
                else:
                    file_info = File.get_most_recent_by_user_and_filename(sender_id, filename)
                
                if file_info:
                    attachment = {
                        "file_id": str(file_info['_id']),
                        "file_type": attachment_type,
                        "filename": file_info.get('original_filename', filename),
                        "mime_type": file_info.get('mime_type', ''),
                        "size": file_info.get('file_size', 0)
                    }
                    message_type = attachment_type
        
        print(f"Final attachment: {attachment}")
        print(f"Message type: {message_type}")

        try:
            # Create a new message using the Message model with proper parameters
            print(f"Creating message in database...")
            message = Message.create(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content=content,
                message_type=message_type,
                attachment=attachment
            )
            print(f"Message created successfully with ID: {message['_id']}")
        except Exception as e:
            print(f"ERROR: Failed to save message to database - {str(e)}")
            emit('error', {'message': 'Failed to save message'})
            return

        try:
            # Fetch sender details from User model
            sender = User.get_by_id(sender_id)
            
            # Emit the message to the room
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


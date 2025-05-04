from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from flask import current_app
from app.models.message import Message  # Import the Message model
from app.models.user import User  # Add User model import
import datetime
import jwt
import logging
import os

# Debug mode for development - set to False in production
DEBUG_MODE = os.environ.get('FLASK_ENV') == 'development'

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
        content = data['content']
        
        # Check if there's a file attachment
        file_id = data.get('file_id')
        file_type = data.get('file_type')
        
        # Create attachment object if file info is provided
        attachment = None
        message_type = "text"
        if file_id:
            print(f"Message contains file attachment: {file_id} (Type: {file_type})")
            attachment = {
                "file_id": file_id,
                "file_type": file_type
            }
            message_type = file_type or "file"  # Use file_type as message_type if provided

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


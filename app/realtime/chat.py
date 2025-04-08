from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from flask import current_app
from app.models.message import Message  # Import the Message model
from app.models.user import User  # Add User model import
import datetime
import jwt
import logging

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
    
    @socketio.on('join')
    def handle_join(data):
        """Handle a user joining a chat room."""
        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        join_room(room)
        emit('status', {'message': f'User joined room {room}'}, room=room)

    @socketio.on('leave')
    def handle_leave(data):
        """Handle a user leaving a chat room."""
        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        leave_room(room)
        emit('status', {'message': f'User left room {room}'}, room=room)

    @socketio.on('send_message')
    def handle_send_message(data):
        """Handle sending a message."""
        logging.info(f"handle_send_message received data: {data}") # Log received data
        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            logging.error("handle_send_message: Invalid or missing token") # Log error
            emit('error', {'message': 'Invalid or missing token'})
            return

        logging.info(f"handle_send_message decoded token: {decoded_token}") # Log decoded token

        room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
        logging.info(f"handle_send_message determined room: {room}") # Log room name
        sender_id = decoded_token['sub']  # Use the user ID from the token
        recipient_id = data['recipient']
        content = data['content']

        try:
            # Create a new message using the Message model
            logging.info(f"handle_send_message attempting to create message: sender={sender_id}, recipient={recipient_id}, content={content}") # Log before create
            message = Message.create(
                sender_id=sender_id,
                recipient_id=recipient_id,
                content=content
            )
            logging.info(f"handle_send_message message created successfully: {message}") # Log after create
        except Exception as e:
            logging.error(f"handle_send_message error creating message: {e}") # Log creation error
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
                'status': message['status']
            }
            logging.info(f"handle_send_message emitting receive_message to room {room}: {message_payload}") # Log before emit
            emit('receive_message', message_payload, room=room)
            logging.info(f"handle_send_message emitted receive_message successfully") # Log after emit
        except Exception as e:
            logging.error(f"handle_send_message error emitting message: {e}") # Log emission error
            # Optionally notify sender of emission failure, though they get the ack below
            pass
        
        # Return acknowledgment to the sender
        ack_payload = {
            'status': 'success',
            'message_id': str(message['_id']),
            'timestamp': message['created_at'].isoformat()
        }
        logging.info(f"handle_send_message returning acknowledgment: {ack_payload}") # Log acknowledgment
        return ack_payload


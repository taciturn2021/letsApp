from flask_socketio import emit, join_room, leave_room
from app import socketio
from app.models.message import Message  # Import the Message model
from flask_jwt_extended import decode_token, JWTDecodeError
from flask import request
import datetime


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
    token = data.get('token')
    decoded_token = validate_token(token)
    if not decoded_token:
        emit('error', {'message': 'Invalid or missing token'})
        return

    room = f"{min(decoded_token['sub'], data['recipient'])}_{max(decoded_token['sub'], data['recipient'])}"
    sender_id = decoded_token['sub']  # Use the user ID from the token
    recipient_id = data['recipient']
    content = data['content']

    # Create a new message using the Message model
    message = Message.create(
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content
    )

    # Emit the message to the room
    emit('receive_message', {
        'id': str(message['_id']),
        'sender': str(message['sender_id']),
        'recipient': str(message['recipient_id']),
        'content': message['content'],
        'timestamp': message['created_at'].isoformat(),
        'status': message['status']
    }, room=room)
    
    
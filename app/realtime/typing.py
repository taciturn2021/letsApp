from flask_socketio import emit
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.realtime import socketio
from app.realtime.events import connected_users

@socketio.on('typing_start')
@jwt_required()
def handle_typing_start(data):
    """Handle typing start event"""
    current_user = get_jwt_identity()
    recipient_id = data.get('recipient_id')
    
    # Validate recipient exists
    if not recipient_id:
        return
    
    # Check if recipient is connected
    if recipient_id in connected_users:
        # Emit typing event to recipient
        emit('typing_indicator', {
            'user_id': current_user,
            'status': 'typing'
        }, room=f"user_{recipient_id}")

@socketio.on('typing_stop')
@jwt_required()
def handle_typing_stop(data):
    """Handle typing stop event"""
    current_user = get_jwt_identity()
    recipient_id = data.get('recipient_id')
    
    # Validate recipient exists
    if not recipient_id:
        return
    
    # Check if recipient is connected
    if recipient_id in connected_users:
        # Emit typing stopped event to recipient
        emit('typing_indicator', {
            'user_id': current_user,
            'status': 'stopped'
        }, room=f"user_{recipient_id}")

# Group typing indicators
@socketio.on('group_typing_start')
@jwt_required()
def handle_group_typing_start(data):
    """Handle group typing start event"""
    current_user = get_jwt_identity()
    group_id = data.get('group_id')
    
    # Validate group exists
    if not group_id:
        return
    
    # Emit to the group room
    emit('group_typing_indicator', {
        'user_id': current_user,
        'group_id': group_id,
        'status': 'typing'
    }, room=f"group_{group_id}")

@socketio.on('group_typing_stop')
@jwt_required()
def handle_group_typing_stop(data):
    """Handle group typing stop event"""
    current_user = get_jwt_identity()
    group_id = data.get('group_id')
    
    # Validate group exists
    if not group_id:
        return
    
    # Emit to the group room
    emit('group_typing_indicator', {
        'user_id': current_user,
        'group_id': group_id,
        'status': 'stopped'
    }, room=f"group_{group_id}")

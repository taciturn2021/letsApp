from flask_socketio import emit
from flask import request
from app.realtime.events import connected_users

def register_handlers(socketio):
    """Register all Socket.IO event handlers for typing indicators"""
    
    @socketio.on('typing_start')
    def handle_typing_start(data):
        """Handle typing start event"""
        # Get the token from request args or headers
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return
        
        current_user = decoded_token['sub']
        recipient_id = data.get('recipient_id')
        
        # Validate recipient exists
        if not recipient_id:
            return
        
        # Check if recipient is connected
        if recipient_id in connected_users:
            # Emit typing event to recipient
            emit('typing_indicator', {
                'user_id': str(current_user),
                'status': 'typing'
            }, room=f"user_{recipient_id}")

    @socketio.on('typing_stop')
    def handle_typing_stop(data):
        """Handle typing stop event"""
        # Get the token from request args or headers
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return
        
        current_user = decoded_token['sub']
        recipient_id = data.get('recipient_id')
        
        # Validate recipient exists
        if not recipient_id:
            return
        
        # Check if recipient is connected
        if recipient_id in connected_users:
            # Emit typing stopped event to recipient
            emit('typing_indicator', {
                'user_id': str(current_user),
                'status': 'stopped'
            }, room=f"user_{recipient_id}")

    # Group typing indicators
    @socketio.on('group_typing_start')
    def handle_group_typing_start(data):
        """Handle group typing start event"""
        # Get the token from request args or headers
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return
        
        current_user = decoded_token['sub']
        group_id = data.get('group_id')
        
        # Validate group exists
        if not group_id:
            return
        
        # Emit to the group room
        emit('group_typing_indicator', {
            'user_id': str(current_user),
            'group_id': group_id,
            'status': 'typing'
        }, room=f"group_{group_id}")

    @socketio.on('group_typing_stop')
    def handle_group_typing_stop(data):
        """Handle group typing stop event"""
        # Get the token from request args or headers
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            emit('error', {'message': 'Invalid or missing token'})
            return
        
        current_user = decoded_token['sub']
        group_id = data.get('group_id')
        
        # Validate group exists
        if not group_id:
            return
        
        # Emit to the group room
        emit('group_typing_indicator', {
            'user_id': str(current_user),
            'group_id': group_id,
            'status': 'stopped'
        }, room=f"group_{group_id}")

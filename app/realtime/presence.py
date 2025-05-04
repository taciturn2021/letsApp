from flask_socketio import emit
from flask_jwt_extended import get_jwt_identity
from app.models.presence import Presence
from app.realtime.events import connected_users

def register_handlers(socketio):
    """Register all Socket.IO event handlers for presence"""
    
    @socketio.on('set_status')
    def handle_set_status(data):
        """Handle status change from client"""
        # Get the token from request args or headers
        from flask import request
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            return {'error': 'Invalid or missing token'}
        
        current_user = decoded_token['sub']
        status = data.get('status')
        
        # Validate status
        valid_statuses = [Presence.STATUS_ONLINE, Presence.STATUS_OFFLINE, Presence.STATUS_AWAY]
        if status not in valid_statuses:
            return {'error': 'Invalid status'}
        
        # Update status in database
        Presence.update_status(current_user, status)
        
        # Notify user's contacts about status change
        from app.utils.db import get_db
        db = get_db()
        
        contacts = db.contacts.find({'contact_id': current_user, 'status': 'accepted'})
        
        # Get user details
        user = db.users.find_one({'_id': current_user}, {'username': 1})
        
        for contact in contacts:
            contact_id = str(contact['user_id'])
            if contact_id in connected_users:
                emit('presence_update', {
                    'user_id': current_user,
                    'username': user['username'],
                    'status': status
                }, room=f"user_{contact_id}")
        
        return {'success': True}

    @socketio.on('get_contacts_status')
    def handle_get_contacts_status(data=None):
        """Get online status of all contacts"""
        # Get the token from request args or headers
        from flask import request
        token = request.args.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        # If data is provided and contains token, use it
        if data and 'token' in data:
            token = data.get('token')
        
        # Validate token
        from app.realtime.chat import validate_token
        decoded_token = validate_token(token)
        if not decoded_token:
            return {'error': 'Invalid or missing token'}
            
        current_user = decoded_token['sub']
        
        # Get contacts with their status
        contacts_status = Presence.get_contacts_status(current_user)
        
        return {'contacts': contacts_status}

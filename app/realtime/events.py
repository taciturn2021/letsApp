from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app.models.presence import Presence
from app.models.user import User
from app.utils.db import get_db

# Store user_id to session_id mapping
connected_users = {}

def register_handlers(socketio):
    """Register all Socket.IO event handlers for connection events"""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        token = request.args.get('token')
        if not token:
            return False  # reject connection
        
        try:
            # Decode token to get user_id
            decoded = decode_token(token)
            user_id = decoded['sub']
            
            # Store the session
            connected_users[user_id] = request.sid
            
            # Join a room specific to this user
            join_room(f"user_{user_id}")
            
            # Update user presence
            Presence.update_status(user_id, Presence.STATUS_ONLINE)
            
            # Get user data
            user = User.get_by_id(user_id)
            
            # Notify user's contacts about online status
            db = get_db()
            contacts = db.contacts.find({"contact_id": user_id, "status": "accepted"})
            
            for contact in contacts:
                contact_id = str(contact['user_id'])
                if contact_id in connected_users:
                    emit('presence_update', {
                        'user_id': user_id,
                        'username': user['username'],
                        'status': Presence.STATUS_ONLINE
                    }, room=f"user_{contact_id}")
                    
            return True
        except Exception as e:
            print(f"WebSocket connection error: {str(e)}")
            return False

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        # Find user_id by session_id
        user_id = None
        for uid, sid in connected_users.items():
            if sid == request.sid:
                user_id = uid
                break
        
        if user_id:
            # Remove from connected users
            connected_users.pop(user_id, None)
            
            # Update presence status
            Presence.update_status(user_id, Presence.STATUS_OFFLINE)
            
            # Get user data
            user = User.get_by_id(user_id)
            
            # Notify user's contacts about offline status
            db = get_db()
            contacts = db.contacts.find({"contact_id": user_id, "status": "accepted"})
            
            for contact in contacts:
                contact_id = str(contact['user_id'])
                if contact_id in connected_users:
                    emit('presence_update', {
                        'user_id': user_id,
                        'username': user['username'],
                        'status': Presence.STATUS_OFFLINE
                    }, room=f"user_{contact_id}")

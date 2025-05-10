from flask_socketio import emit
from flask_jwt_extended import get_jwt_identity
from app.models.presence import Presence
from app.realtime.events import connected_users
import datetime

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
        valid_statuses = [Presence.STATUS_ONLINE, Presence.STATUS_OFFLINE]
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
                    'user_id': str(current_user),
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
        
        # Convert ObjectId to string in the response
        for contact in contacts_status:
            contact['user_id'] = str(contact['user_id'])
        
        return {'contacts': contacts_status}

    @socketio.on('get_users_status')
    def handle_get_users_status(data=None):
        """Get online status of all users"""
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
        
        # Get all users from database
        from app.utils.db import get_db
        db = get_db()
        
        # Fetch all users except the current one
        users = list(db.users.find(
            {"_id": {"$ne": current_user}},
            {"username": 1, "profile_picture": 1}
        ))
        
        # Get presence information for all users
        user_ids = [user["_id"] for user in users]
        presence_list = list(db.presence.find({
            "user_id": {"$in": user_ids}
        }))
        
        # Create a lookup dictionary for presence data
        presence_by_id = {str(p["user_id"]): p for p in presence_list}
        
        # Combine the data
        result = []
        for user in users:
            user_id_str = str(user["_id"])
            presence_data = presence_by_id.get(user_id_str, {})
            
            # Check if online status is stale (more than 10 minutes old)
            status = presence_data.get("status", Presence.STATUS_OFFLINE)
            if status == Presence.STATUS_ONLINE:
                if "last_updated" in presence_data:
                    time_diff = datetime.datetime.utcnow() - presence_data["last_updated"]
                    if time_diff.total_seconds() > 600:  # 10 minutes instead of 2
                        status = Presence.STATUS_OFFLINE
            
            # Convert datetime objects to ISO format strings
            last_active = presence_data.get("last_active")
            if last_active:
                last_active = last_active.isoformat()
            
            result.append({
                "user_id": str(user["_id"]),
                "username": user["username"],
                "profile_picture": user.get("profile_picture"),
                "status": status,
                "last_active": last_active
            })
        
        return {'users': result}

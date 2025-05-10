from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app.models.presence import Presence
from app.models.user import User
from app.utils.db import get_db
import threading
import time

# Store user_id to session_id mapping
connected_users = {}

def register_handlers(socketio):
    """Register all Socket.IO event handlers for connection events"""
    
    # Start a background thread for heartbeat
    def heartbeat_thread():
        """Periodically refresh presence status for all connected users"""
        while True:
            time.sleep(60)  # Run every minute
            try:
                # For each connected user, refresh their presence status
                for user_id in list(connected_users.keys()):
                    try:
                        Presence.update_status(user_id, Presence.STATUS_ONLINE)
                        print(f"Refreshed online status for user {user_id}")
                    except Exception as e:
                        print(f"Error refreshing presence for {user_id}: {str(e)}")
            except Exception as e:
                print(f"Error in heartbeat thread: {str(e)}")
    
    # Start the heartbeat thread
    thread = threading.Thread(target=heartbeat_thread, daemon=True)
    thread.start()
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print("\n========== WEBSOCKET: Client Connected ==========")
        token = request.args.get('token')
        if not token:
            print("ERROR: No token provided for connection")
            return False  # reject connection
        
        try:
            # Decode token to get user_id
            decoded = decode_token(token)
            user_id = decoded['sub']
            print(f"SUCCESS: User {user_id} connected with token")
            
            # Store the session
            connected_users[user_id] = request.sid
            print(f"SUCCESS: Added user {user_id} to connected_users map")
            
            # Join a room specific to this user
            join_room(f"user_{user_id}")
            print(f"SUCCESS: User {user_id} joined their personal room")
            
            # Update user presence
            Presence.update_status(user_id, Presence.STATUS_ONLINE)
            print(f"SUCCESS: User {user_id} status set to ONLINE in database")
            
            # Get user data
            user = User.get_by_id(user_id)
            print(f"SUCCESS: Retrieved user data for {user_id}")
            
            # Log current presence state
            print(f"PRESENCE DEBUG: Current connected_users: {list(connected_users.keys())}")
            
            # Notify user's contacts about online status
            db = get_db()
            contacts = db.contacts.find({"contact_id": user_id, "status": "accepted"})
            
            for contact in contacts:
                contact_id = str(contact['user_id'])  # Convert ObjectId to string
                if contact_id in connected_users:
                    emit('presence_update', {
                        'user_id': str(user_id),  # Convert ObjectId to string
                        'username': user['username'],
                        'status': Presence.STATUS_ONLINE
                    }, room=f"user_{contact_id}")
                    
            return True
        except Exception as e:
            print(f"ERROR: WebSocket connection error: {str(e)}")
            import traceback
            traceback.print_exc()
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
                contact_id = str(contact['user_id'])  # Convert ObjectId to string
                if contact_id in connected_users:
                    emit('presence_update', {
                        'user_id': str(user_id),  # Convert ObjectId to string
                        'username': user['username'],
                        'status': Presence.STATUS_OFFLINE
                    }, room=f"user_{contact_id}")

    @socketio.on('heartbeat')
    def handle_heartbeat(data=None):
        """Handle heartbeat from client to refresh presence"""
        sid = request.sid
        user_id = None
        
        # Find the user ID for this session
        for uid, session_id in connected_users.items():
            if session_id == sid:
                user_id = uid
                break
                
        if user_id:
            # Refresh the user's online status
            Presence.update_status(user_id, Presence.STATUS_ONLINE)
            return {"success": True}
        
        return {"success": False, "error": "User not found"}

from flask_socketio import emit
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.realtime import socketio
from app.models.presence import Presence
from app.realtime.events import connected_users

@socketio.on('set_status')
@jwt_required()
def handle_set_status(data):
    """Handle status change from client"""
    current_user = get_jwt_identity()
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
@jwt_required()
def handle_get_contacts_status():
    """Get online status of all contacts"""
    current_user = get_jwt_identity()
    
    # Get contacts with their status
    contacts_status = Presence.get_contacts_status(current_user)
    
    return {'contacts': contacts_status}

from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from flask import current_app
from app.models.group import Group
from app.models.user import User
from app.models.group_message import GroupMessage
from app.realtime.events import connected_users
import datetime
import logging
import os
import json

DEBUG_MODE = os.environ.get('FLASK_ENV') == 'development'

logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

def validate_token(token):
    """Validate JWT token and return the decoded token or None if invalid"""
    if not token:
        return None
    try:
        decoded_token = decode_token(token)
        return decoded_token
    except Exception:  
        return None

def register_handlers(socketio):
    """Register all Socket.IO event handlers for group chat"""
    
    @socketio.on('group_created')
    def handle_group_created(data):
        """Handle group creation notification"""
        try:
            # Get the JWT token from the auth header or connection
            token = data.get('token')
            if not token:
                emit('error', {'message': 'Authentication required'})
                return
            
            # Decode token to get user info
            decoded_token = decode_token(token)
            current_user_id = decoded_token['sub']
            
            group_id = data.get('group_id')
            group_name = data.get('group_name')
            member_ids = data.get('member_ids', [])
            
            if not all([group_id, group_name, member_ids]):
                emit('error', {'message': 'Missing required group data'})
                return
            
            # Get creator info
            creator = User.get_by_id(current_user_id)
            creator_name = creator.get('username', 'Unknown User') if creator else 'Unknown User'
            
            # Notify each member (except creator) that they've been added to a group
            for member_id in member_ids:
                if str(member_id) != str(current_user_id):
                    socketio.emit('group_added', {
                        'group_id': group_id,
                        'group_name': group_name,
                        'creator_name': creator_name,
                        'timestamp': datetime.datetime.now(timezone.utc).isoformat()
                    }, room=f'user_{member_id}')
            
            print(f"Group creation notifications sent for group {group_id}")
            
        except Exception as e:
            print(f"Error handling group creation: {str(e)}")
            emit('error', {'message': 'Failed to process group creation'})

    @socketio.on('member_added_to_group')
    def handle_member_added(data):
        """Handle member addition to group"""
        try:
            group_id = data.get('group_id')
            group_name = data.get('group_name')
            admin_name = data.get('admin_name')
            member_id = data.get('member_id')
            
            if not all([group_id, group_name, admin_name, member_id]):
                emit('error', {'message': 'Missing required data for member addition'})
                return
            
            # Notify the added member
            socketio.emit('member_added_to_group', {
                'group_id': group_id,
                'group_name': group_name,
                'admin_name': admin_name,
                'timestamp': datetime.datetime.now(timezone.utc).isoformat()
            }, room=f'user_{member_id}')
            
            # Notify all other group members about the new member
            group = Group.get_by_id(group_id)
            if group:
                added_user = User.get_by_id(member_id)
                added_username = added_user.get('username', 'Unknown User') if added_user else 'Unknown User'
                
                for existing_member_id in group['members']:
                    if str(existing_member_id) != str(member_id):  # Don't notify the added member again
                        socketio.emit('group_member_added', {
                            'group_id': group_id,
                            'group_name': group_name,
                            'added_member_name': added_username,
                            'admin_name': admin_name,
                            'timestamp': datetime.datetime.now(timezone.utc).isoformat()
                        }, room=f'user_{existing_member_id}')
            
            print(f"Member addition notifications sent for group {group_id}")
            
        except Exception as e:
            print(f"Error handling member addition: {str(e)}")
            emit('error', {'message': 'Failed to process member addition'})

    @socketio.on('member_removed_from_group')
    def handle_member_removed(data):
        """Handle member removal from group"""
        try:
            group_id = data.get('group_id')
            group_name = data.get('group_name')
            admin_name = data.get('admin_name')
            removed_member_id = data.get('removed_member_id')
            removed_member_name = data.get('removed_member_name')
            removed_by_self = data.get('removed_by_self', False)
            
            if not all([group_id, group_name, removed_member_id, removed_member_name]):
                emit('error', {'message': 'Missing required data for member removal'})
                return
            
            # Notify the removed member
            socketio.emit('member_removed_from_group', {
                'group_id': group_id,
                'group_name': group_name,
                'admin_name': admin_name,
                'removed_by_self': removed_by_self,
                'timestamp': datetime.datetime.now(timezone.utc).isoformat()
            }, room=f'user_{removed_member_id}')
            
            # Notify remaining group members about the removal
            group = Group.get_by_id(group_id)
            if group:
                for remaining_member_id in group['members']:
                    socketio.emit('group_member_removed', {
                        'group_id': group_id,
                        'group_name': group_name,
                        'removed_member_name': removed_member_name,
                        'admin_name': admin_name,
                        'removed_by_self': removed_by_self,
                        'timestamp': datetime.datetime.now(timezone.utc).isoformat()
                    }, room=f'user_{remaining_member_id}')
            
            print(f"Member removal notifications sent for group {group_id}")
            
        except Exception as e:
            print(f"Error handling member removal: {str(e)}")
            emit('error', {'message': 'Failed to process member removal'})

    @socketio.on('group_name_updated')
    def handle_group_name_updated(data):
        """Handle group name update"""
        try:
            group_id = data.get('group_id')
            old_name = data.get('old_name')
            new_name = data.get('new_name')
            admin_name = data.get('admin_name')
            
            if not all([group_id, old_name, new_name, admin_name]):
                emit('error', {'message': 'Missing required data for group name update'})
                return
            
            # Notify all group members about the name change
            group = Group.get_by_id(group_id)
            if group:
                for member_id in group['members']:
                    socketio.emit('group_name_updated', {
                        'group_id': group_id,
                        'old_name': old_name,
                        'new_name': new_name,
                        'admin_name': admin_name,
                        'timestamp': datetime.datetime.now(timezone.utc).isoformat()
                    }, room=f'user_{member_id}')
            
            print(f"Group name update notifications sent for group {group_id}")
            
        except Exception as e:
            print(f"Error handling group name update: {str(e)}")
            emit('error', {'message': 'Failed to process group name update'})

    @socketio.on('join_group')
    def handle_join_group(data):
        """Handle user joining a group room"""
        try:
            group_id = data.get('group_id')
            if group_id:
                join_room(f'group_{group_id}')
                print(f"User joined group room: group_{group_id}")
        except Exception as e:
            print(f"Error joining group room: {str(e)}")
    
    @socketio.on('leave_group')
    def handle_leave_group(data):
        """Handle user leaving a group room"""
        try:
            group_id = data.get('group_id')
            if group_id:
                leave_room(f'group_{group_id}')
                print(f"User left group room: group_{group_id}")
        except Exception as e:
            print(f"Error leaving group room: {str(e)}") 
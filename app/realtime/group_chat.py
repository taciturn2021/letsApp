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

    @socketio.on('send_group_message')
    def handle_send_group_message(data):
        """Handle sending a message to a group."""
        print("\n========== WEBSOCKET: NEW GROUP MESSAGE RECEIVED ==========")
        print(f"Raw group message data from client: {data}") 
        
        client_attachment_payload = data.get('attachment')
        if client_attachment_payload:
            print(f"Client attachment payload received: {client_attachment_payload}")
            print(f"Keys in client_attachment_payload: {list(client_attachment_payload.keys()) if isinstance(client_attachment_payload, dict) else 'Not a dict'}")

        token = data.get('token')
        decoded_token = validate_token(token)
        if not decoded_token:
            print("ERROR: Invalid or missing token")
            emit('error', {'message': 'Invalid or missing token'})
            return

        print(f"Token validated for user: {decoded_token['sub']}")

        sender_id = decoded_token['sub']
        group_id = data.get('group_id')
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')
        
        # Validate group exists and user is a member
        group = Group.get_by_id(group_id)
        if not group:
            print(f"ERROR: Group {group_id} not found")
            emit('error', {'message': 'Group not found'})
            return
        
        from bson import ObjectId
        if ObjectId(sender_id) not in group['members']:
            print(f"ERROR: User {sender_id} is not a member of group {group_id}")
            emit('error', {'message': 'You are not a member of this group'})
            return
        
        print(f"Group message room: group_{group_id}")
        
        attachment_to_save = None # Renamed from 'attachment' to avoid confusion
        
        if client_attachment_payload and isinstance(client_attachment_payload, dict):
           
            media_doc_id = client_attachment_payload.get('fileId') 
            
        
            if not media_doc_id:
                media_doc_id = client_attachment_payload.get('file_id')

            original_filename = client_attachment_payload.get('filename')
            
            resolved_file_type = client_attachment_payload.get('type') or client_attachment_payload.get('file_type') or 'document' 

            print(f"Processing client attachment: media_doc_id='{media_doc_id}', filename='{original_filename}', type='{resolved_file_type}'")

            file_info = None
            if media_doc_id and media_doc_id not in ['undefined', 'null', None, '']:
                print(f"Attempting to fetch Media/File object using ID: {media_doc_id} (type hint: {resolved_file_type})")
                from app.models.media import Media
                from app.models.file import File
                if resolved_file_type in ('image', 'video', 'audio'):
                    file_info = Media.get_by_id(media_doc_id)
                else:
                    file_info = File.get_by_id(media_doc_id)
                
                if file_info:
                    print(f"Successfully fetched by ID: {file_info['_id']}")
                else:
                    # If ID lookup fails, maybe it was a filename passed as fileId by mistake, or bad ID
                    print(f"WARN: Could not find Media/File for ID: {media_doc_id}. Will try filename lookup if available.")
            
            # If file_info not found by ID, AND we have an original_filename, try by filename
            if not file_info and original_filename:
                print(f"Attempting to fetch by filename: '{original_filename}' for user '{sender_id}' (type hint: {resolved_file_type})")
                if resolved_file_type in ('image', 'video', 'audio'):
                    file_info = Media.get_most_recent_by_user_and_filename(sender_id, original_filename)
                else:
                    file_info = File.get_most_recent_by_user_and_filename(sender_id, original_filename)
                
                if file_info:
                    print(f"Successfully fetched by filename: {file_info['_id']}")
                else:
                    print(f"WARN: Could not find Media/File by filename: {original_filename}")

            if file_info:
                # Determine the most reliable message_type from the retrieved file_info
                message_type = file_info.get('media_type') or file_info.get('file_type') or resolved_file_type
                attachment_to_save = {
                    "file_id": str(file_info['_id']),
                    "file_type": message_type,
                    "filename": file_info.get('original_filename', original_filename or ''),
                    "mime_type": file_info.get('mime_type', ''),
                    "size": file_info.get('file_size', 0)
                }
            else:
                print(f"ERROR: Attachment processing failed. No file_info found for: {client_attachment_payload}")
                # Keep original message_type if attachment fails, or reset if it was file-specific
                if message_type not in ['text'] and not content: # If it was e.g. 'video' but no content and attach failed
                    message_type = 'text' # Default to text if attachment fails and no content
        
        print(f"Final attachment to save in DB: {attachment_to_save}")
        print(f"Final message_type for DB: {message_type}")

        try:
            print(f"Creating group message in database...")
            message = GroupMessage.create(
                group_id=group_id,
                sender_id=sender_id,
                content=content,
                message_type=message_type,
                attachment=attachment_to_save # Use the processed attachment_to_save
            )
            print(f"Group message created successfully with ID: {message['_id']}")
        except Exception as e:
            print(f"ERROR: Failed to save group message to database - {str(e)}")
            emit('error', {'message': 'Failed to save group message'})
            return

        try:
            # Fetch sender details from User model
            sender = User.get_by_id(sender_id)
            
            # Convert ObjectId and datetime objects to strings
            message_payload = {
                'id': str(message['_id']),
                'group_id': str(message['group_id']),
                'sender': str(message['sender_id']),
                'sender_name': sender.get('username', ''),  # Use username as sender_name
                'sender_avatar': sender.get('profile_picture', ''),  # Use profile_picture as sender_avatar
                'content': message['content'],
                'timestamp': message['created_at'].isoformat(),
                'message_type': message['message_type'],
                'attachment': message['attachment'],
                'read_by': [str(user_id) for user_id in message.get('read_by', [])]
            }
            
            # Broadcast to all group members except the sender to avoid duplicates
            print(f"Broadcasting group message to group members (excluding sender {sender_id})")
            for member_id in group['members']:
                member_id_str = str(member_id)
                if member_id_str != sender_id:  # Exclude the sender
                    emit('receive_group_message', message_payload, room=f'user_{member_id_str}')
                    print(f"Sent group message to member: {member_id_str}")
            
            print(f"Group message broadcast successful (excluded sender)")
        except Exception as e:
            print(f"ERROR: Failed to broadcast group message - {str(e)}")
            # Optionally notify sender of emission failure
            pass
        
        # Return acknowledgment to the sender
        ack_payload = {
            'status': 'success',
            'message_id': str(message['_id']),
            'timestamp': message['created_at'].isoformat()
        }
        print(f"Sending acknowledgment to sender: {ack_payload}")
        print("========== GROUP MESSAGE PROCESSING COMPLETE ==========\n")
        return ack_payload 
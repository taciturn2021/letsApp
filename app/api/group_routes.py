from flask import jsonify, request, Blueprint
from app import mongo
from app.models import Group, User, Media
from app.utils.file_handler import save_group_icon
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
import os
from flask import current_app
import datetime
from datetime import timezone

bp = Blueprint('groups', __name__)

@bp.route('/create', methods=['POST'])
@jwt_required()
def create_group():
    """Create a new group chat"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({"success": False, "message": "Group name is required"}), 400
    
    if not data.get('members') or not isinstance(data.get('members'), list):
        return jsonify({"success": False, "message": "Members list is required"}), 400
    
    # Create group
    try:
        # Get member IDs
        member_ids = [member['id'] for member in data.get('members', [])]
        
        # Add creator to members if not already included
        if current_user_id not in member_ids:
            member_ids.append(current_user_id)
            
        # Create the group
        group = Group.create(
            name=data['name'],
            creator_id=current_user_id,
            description=data.get('description', '')
        )
        
        # Add members (creator is already added in Group.create)
        for member_id in member_ids:
            if str(member_id) != str(current_user_id):  # Skip creator as they're already added
                Group.add_member(group['_id'], member_id, current_user_id)
        
        # Refresh group data to get all members
        updated_group = Group.get_by_id(group['_id'])
        
        # Get creator details for response
        creator = User.get_by_id(current_user_id)
        creator_name = creator.get('username', 'Unknown User') if creator else 'Unknown User'
        
        # Format response with updated member list
        response_data = {
            "group_id": str(updated_group['_id']),
            "name": updated_group['name'],
            "creator_id": str(updated_group['creator_id']),
            "creator_name": creator_name,
            "members": [str(member_id) for member_id in updated_group['members']],
            "created_at": updated_group['created_at'].isoformat()
        }
        
        return jsonify({
            "success": True, 
            "message": "Group created successfully",
            "data": response_data
        }), 201
        
    except Exception as e:
        print(f"Error creating group: {str(e)}")
        return jsonify({"success": False, "message": f"Error creating group: {str(e)}"}), 500

@bp.route('/list', methods=['GET'])
@jwt_required()
def get_user_groups():
    """Get all groups for the current user"""
    current_user_id = get_jwt_identity()
    
    try:
        print(f"\n===== GROUP LIST REQUEST =====")
        print(f"Current user ID: {current_user_id}")
        
        # Get groups
        groups = Group.get_user_groups(current_user_id)
        print(f"Found {len(groups)} groups for user {current_user_id}")
        
        if groups:
            print("Group details:")
            for group in groups:
                print(f"  - Group ID: {group['_id']}, Name: {group['name']}, Members: {group['members']}")
        
        # Format response
        formatted_groups = []
        for group in groups:
            # Get member details
            members = []
            for member_id in group['members']:
                member = User.get_by_id(member_id)
                if member:
                    members.append({
                        "id": str(member['_id']),
                        "username": member.get('username', 'Unknown User')
                    })
            
            formatted_groups.append({
                "id": str(group['_id']),
                "name": group['name'],
                "description": group.get('description', ''),
                "icon": group.get('icon'),
                "creator_id": str(group['creator_id']),
                "members": members,
                "created_at": group['created_at'].isoformat(),
                "updated_at": group['updated_at'].isoformat()
            })
        
        print(f"Returning {len(formatted_groups)} formatted groups")
        print("===== GROUP LIST RESPONSE =====\n")
        
        return jsonify({
            "success": True,
            "data": formatted_groups
        }), 200
        
    except Exception as e:
        print(f"Error getting user groups: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting user groups: {str(e)}"}), 500

@bp.route('/<group_id>/info', methods=['GET'])
@jwt_required()
def get_group_info(group_id):
    """Get detailed information about a group"""
    current_user_id = get_jwt_identity()
    
    try:
        # Get group
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        # Check if user is a member
        if ObjectId(current_user_id) not in group['members']:
            return jsonify({"success": False, "message": "You are not a member of this group"}), 403
        
        # Get creator details
        creator = User.get_by_id(group['creator_id'])
        creator_name = creator.get('username', 'Unknown User') if creator else 'Unknown User'
        
        # Get member details
        members = []
        for member_id in group['members']:
            member = User.get_by_id(member_id)
            if member:
                is_admin = ObjectId(member_id) in group['admins']
                members.append({
                    "id": str(member['_id']),
                    "username": member.get('username', 'Unknown User'),
                    "profile_picture": member.get('profile_picture'),
                    "is_admin": is_admin
                })
        
        # Get admin details
        admin_ids = [str(admin_id) for admin_id in group['admins']]
        
        # Check if current user is admin
        is_current_user_admin = ObjectId(current_user_id) in group['admins']
        
        group_info = {
            "id": str(group['_id']),
            "name": group['name'],
            "description": group.get('description', ''),
            "icon": group.get('icon'),
            "creator_id": str(group['creator_id']),
            "creator_name": creator_name,
            "members": members,
            "admin_ids": admin_ids,
            "is_current_user_admin": is_current_user_admin,
            "member_count": len(group['members']),
            "created_at": group['created_at'].isoformat(),
            "updated_at": group['updated_at'].isoformat()
        }
        
        return jsonify({
            "success": True,
            "data": group_info
        }), 200
        
    except Exception as e:
        print(f"Error getting group info: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting group info: {str(e)}"}), 500

@bp.route('/<group_id>/icon', methods=['POST'])
@jwt_required()
def upload_group_icon(group_id):
    """Upload a new group icon (admin only)"""
    current_user_id = get_jwt_identity()
    
    try:
        # Check if group exists and user is admin
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        if ObjectId(current_user_id) not in group['admins']:
            return jsonify({"success": False, "message": "Only group admins can change the group icon"}), 403
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400
        
        # Create upload folder if it doesn't exist
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'group_icons')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save the file
        result = save_group_icon(file, current_user_id, upload_folder)
        
        if not result["success"]:
            return jsonify(result), 400
        
        # Delete old icon if exists
        if group.get("icon"):
            try:
                Media.delete(group["icon"], current_user_id)
            except Exception as e:
                print(f"Warning: Could not delete old group icon: {str(e)}")
        
        # Update group with new icon
        update_result = Group.update_icon(group_id, result["media_id"], current_user_id)
        
        if update_result:
            return jsonify({
                "success": True,
                "message": "Group icon updated successfully",
                "icon": result["media_id"]
            }), 200
        else:
            return jsonify({"success": False, "message": "Failed to update group icon"}), 500
        
    except Exception as e:
        print(f"Error uploading group icon: {str(e)}")
        return jsonify({"success": False, "message": f"Error uploading group icon: {str(e)}"}), 500

@bp.route('/<group_id>/icon', methods=['DELETE'])
@jwt_required()
def delete_group_icon(group_id):
    """Delete group icon (admin only)"""
    current_user_id = get_jwt_identity()
    
    try:
        # Check if group exists and user is admin
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        if ObjectId(current_user_id) not in group['admins']:
            return jsonify({"success": False, "message": "Only group admins can remove the group icon"}), 403
        
        if not group.get("icon"):
            return jsonify({"success": False, "message": "Group has no icon to remove"}), 400
        
        # Delete the icon file
        try:
            Media.delete(group["icon"], current_user_id)
        except Exception as e:
            print(f"Warning: Could not delete group icon file: {str(e)}")
        
        # Remove icon from group
        result = Group.remove_icon(group_id, current_user_id)
        
        if result:
            return jsonify({
                "success": True,
                "message": "Group icon removed successfully"
            }), 200
        else:
            return jsonify({"success": False, "message": "Failed to remove group icon"}), 500
        
    except Exception as e:
        print(f"Error deleting group icon: {str(e)}")
        return jsonify({"success": False, "message": f"Error deleting group icon: {str(e)}"}), 500

@bp.route('/<group_id>/members', methods=['POST'])
@jwt_required()
def add_member_to_group(group_id):
    """Add a member to a group (admin only)"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or not data.get('user_id'):
        return jsonify({"success": False, "message": "User ID is required"}), 400
    
    try:
        # Check if group exists and user is admin
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        if ObjectId(current_user_id) not in group['admins']:
            return jsonify({"success": False, "message": "Only group admins can add members"}), 403
        
        # Check if user to add exists
        user_to_add = User.get_by_id(data['user_id'])
        if not user_to_add:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Add member to group
        result = Group.add_member(group_id, data['user_id'], current_user_id)
        
        if result:
            # Get updated group info
            updated_group = Group.get_by_id(group_id)
            admin_user = User.get_by_id(current_user_id)
            
            # Emit WebSocket event for member addition
            try:
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('member_added_to_group', {
                        'group_id': group_id,
                        'group_name': updated_group['name'],
                        'admin_name': admin_user.get('username', 'Admin'),
                        'member_id': str(user_to_add['_id'])
                    })
                    print("WebSocket event emitted: member_added_to_group")
                else:
                    print("SocketIO instance not available")
            except Exception as socket_error:
                print(f"WebSocket emission failed: {socket_error}")
            
            return jsonify({
                "success": True,
                "message": "Member added successfully",
                "member": {
                    "id": str(user_to_add['_id']),
                    "username": user_to_add.get('username', 'Unknown User'),
                    "profile_picture": user_to_add.get('profile_picture'),
                    "is_admin": ObjectId(data['user_id']) in updated_group['admins']
                },
                "group_data": {
                    "group_id": group_id,
                    "group_name": updated_group['name'],
                    "admin_name": admin_user.get('username', 'Admin'),
                    "member_id": str(user_to_add['_id'])
                }
            }), 200
        else:
            return jsonify({"success": False, "message": "Failed to add member or user is already a member"}), 400
        
    except Exception as e:
        print(f"Error adding member to group: {str(e)}")
        return jsonify({"success": False, "message": f"Error adding member: {str(e)}"}), 500

@bp.route('/<group_id>/members/<user_id>', methods=['DELETE'])
@jwt_required()
def remove_member_from_group(group_id, user_id):
    """Remove a member from a group (admin only or self-removal)"""
    current_user_id = get_jwt_identity()
    
    try:
        # Check if group exists
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        # Check permissions (admin or self-removal)
        is_admin = ObjectId(current_user_id) in group['admins']
        is_self_removal = str(user_id) == str(current_user_id)
        
        if not is_admin and not is_self_removal:
            return jsonify({"success": False, "message": "You can only remove yourself or be an admin to remove others"}), 403
        
        # Prevent removing the last admin
        if str(user_id) in [str(admin_id) for admin_id in group['admins']] and len(group['admins']) == 1:
            return jsonify({"success": False, "message": "Cannot remove the last admin from the group"}), 400
        
        # Get user info before removal
        user_to_remove = User.get_by_id(user_id)
        if not user_to_remove:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Remove member from group
        result = Group.remove_member(group_id, user_id, current_user_id)
        
        if result:
            admin_user = User.get_by_id(current_user_id)
            
            # Emit WebSocket event for member removal
            try:
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    # Always notify the removed member (whether self-removal or admin removal)
                    current_app.socketio.emit('member_removed_from_group', {
                        'group_id': group_id,
                        'group_name': group['name'],
                        'admin_name': admin_user.get('username', 'Admin'),
                        'removed_by_self': is_self_removal
                    }, room=f'user_{user_id}')
                    print(f"Sent 'member_removed_from_group' to user {user_id} (self_removal: {is_self_removal})")
                    
                    # Notify all remaining group members about the removal (exclude the removed member)
                    updated_group = Group.get_by_id(group_id)
                    for member_id in updated_group['members']:
                        member_id_str = str(member_id)
                        # Don't notify the removed member
                        if member_id_str != str(user_id):
                            current_app.socketio.emit('group_member_removed', {
                                'group_id': group_id,
                                'group_name': group['name'],
                                'removed_member_id': str(user_to_remove['_id']),
                                'removed_member_name': user_to_remove.get('username', 'Unknown User'),
                                'admin_name': admin_user.get('username', 'Admin'),
                                'removed_by_self': is_self_removal,
                                'timestamp': datetime.datetime.now(timezone.utc).isoformat()
                            }, room=f'user_{member_id}')
                            print(f"Sent 'group_member_removed' to member {member_id_str}")
                    
                    print(f"WebSocket events emitted for member removal - removed user {user_id} notified")
                else:
                    print("SocketIO instance not available")
            except Exception as socket_error:
                print(f"WebSocket emission failed: {socket_error}")
                import traceback
                traceback.print_exc()
            
            return jsonify({
                "success": True,
                "message": "Member removed successfully",
                "removed_member": {
                    "id": str(user_to_remove['_id']),
                    "username": user_to_remove.get('username', 'Unknown User')
                },
                "group_data": {
                    "group_id": group_id,
                    "group_name": group['name'],
                    "admin_name": admin_user.get('username', 'Admin'),
                    "removed_by_self": is_self_removal
                }
            }), 200
        else:
            return jsonify({"success": False, "message": "Failed to remove member"}), 400
        
    except Exception as e:
        print(f"Error removing member from group: {str(e)}")
        return jsonify({"success": False, "message": f"Error removing member: {str(e)}"}), 500

@bp.route('/<group_id>/name', methods=['PUT'])
@jwt_required()
def update_group_name(group_id):
    """Update group name (admin only)"""
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or not data.get('name'):
        return jsonify({"success": False, "message": "Group name is required"}), 400
    
    new_name = data['name'].strip()
    if not new_name:
        return jsonify({"success": False, "message": "Group name cannot be empty"}), 400
    
    try:
        # Check if group exists and user is admin
        group = Group.get_by_id(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found"}), 404
        
        if ObjectId(current_user_id) not in group['admins']:
            return jsonify({"success": False, "message": "Only group admins can update the group name"}), 403
        
        # Update group name
        result = Group.update(group_id, {"name": new_name}, current_user_id)
        
        if result:
            admin_user = User.get_by_id(current_user_id)
            
            # Emit WebSocket event for group name update
            try:
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('group_name_updated', {
                        'group_id': group_id,
                        'old_name': group['name'],
                        'new_name': new_name,
                        'admin_name': admin_user.get('username', 'Admin')
                    })
                    print("WebSocket event emitted: group_name_updated")
                else:
                    print("SocketIO instance not available")
            except Exception as socket_error:
                print(f"WebSocket emission failed: {socket_error}")
            
            return jsonify({
                "success": True,
                "message": "Group name updated successfully",
                "group_data": {
                    "group_id": group_id,
                    "old_name": group['name'],
                    "new_name": new_name,
                    "admin_name": admin_user.get('username', 'Admin')
                }
            }), 200
        else:
            return jsonify({"success": False, "message": "Failed to update group name"}), 500
        
    except Exception as e:
        print(f"Error updating group name: {str(e)}")
        return jsonify({"success": False, "message": f"Error updating group name: {str(e)}"}), 500

@bp.route('/<group_id>/messages', methods=['POST'])
@jwt_required()
def send_group_message(group_id):
    """Send a message to a group with proper attachment handling"""
    current_user_id = get_jwt_identity()
    
    # Check if user is a member of the group
    group = Group.get_by_id(group_id)
    if not group:
        return jsonify({"success": False, "message": "Group not found"}), 404
    
    if ObjectId(current_user_id) not in group['members']:
        return jsonify({"success": False, "message": "You are not a member of this group"}), 403
    
    data = request.json
    
    print(f"\n[GROUP API] Sending message from {current_user_id} to group {group_id}")
    print(f"[GROUP API] Message data: {data}")
    
    content = data.get('content', '')
    message_type = data.get('message_type', 'text')
    
    # Process attachment if present
    attachment = None
    if data.get('attachment'):
        attachment_data = data.get('attachment')
        
        # Ensure we have a valid file_id
        if attachment_data.get('file_id') and attachment_data.get('file_id') != 'undefined':
            attachment = attachment_data
            print(f"[GROUP API] Using attachment with file_id: {attachment_data.get('file_id')}")
            
            # If message type is not set, derive it from attachment type
            if message_type == 'text' and attachment_data.get('file_type'):
                message_type = attachment_data.get('file_type')
        else:
            print(f"[GROUP API] Warning: Invalid file_id in attachment: {attachment_data.get('file_id')}")
    
    try:
        # Import GroupMessage here to avoid circular imports
        from app.models.group_message import GroupMessage
        
        # Create the group message
        message = GroupMessage.create(
            group_id=group_id,
            sender_id=current_user_id,
            content=content,
            message_type=message_type,
            attachment=attachment
        )
        
        # Get sender details
        sender = User.get_by_id(current_user_id)
        
        # Format the response
        formatted_message = {
            "id": str(message["_id"]),
            "group_id": str(message["group_id"]),
            "sender": str(message["sender_id"]),
            "sender_name": sender.get("username", ""),
            "sender_avatar": sender.get("profile_picture", ""),
            "content": message["content"],
            "timestamp": message["created_at"].isoformat(),
            "message_type": message.get("message_type", "text"),
            "attachment": message.get("attachment"),
            "read_by": [str(user_id) for user_id in message.get("read_by", [])]
        }
        
        # Emit a socket.io event to notify group members about the new message
        from flask_socketio import emit
        from app.realtime.events import connected_users
        
        try:
            # Get the attachment object/null from the created message
            attachment_obj = message.get('attachment')

            # Emit the message to the group room
            emit('receive_group_message', {
                'id': str(message['_id']),
                'group_id': str(message['group_id']),
                'sender': str(message['sender_id']),
                'sender_name': sender.get('username', ''),
                'sender_avatar': sender.get('profile_picture', ''),
                'content': message['content'],
                'timestamp': message['created_at'].isoformat(),
                'message_type': message['message_type'],
                # Format as an array for the frontend
                'attachments': [attachment_obj] if attachment_obj else [],
                'read_by': [str(user_id) for user_id in message.get('read_by', [])]
            }, room=f"group_{group_id}", namespace='/')
            
            print(f"[GROUP API] Message notification sent to group room: group_{group_id}")
        except Exception as e:
            print(f"[GROUP API] Error emitting socket event: {str(e)}")
        
        print(f"[GROUP API] Group message sent successfully with ID: {str(message['_id'])}")
        return jsonify({
            "success": True,
            "message": "Group message sent successfully",
            "data": formatted_message
        })
    except Exception as e:
        print(f"[GROUP API] ❌ Error sending group message: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error sending group message: {str(e)}"
        }), 500

@bp.route('/<group_id>/messages', methods=['GET'])
@jwt_required()
def get_group_messages(group_id):
    """Get messages for a group with pagination"""
    current_user_id = get_jwt_identity()
    
    # Check if user is a member of the group
    group = Group.get_by_id(group_id)
    if not group:
        return jsonify({"success": False, "message": "Group not found"}), 404
    
    if ObjectId(current_user_id) not in group['members']:
        return jsonify({"success": False, "message": "You are not a member of this group"}), 403
    
    # Use the page/limit provided by the client, defaulting to 1 and 20 if not present
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    print(f"\n[GROUP API ROUTE] Getting messages for group {group_id}")
    print(f"[GROUP API ROUTE] Page: {page}, Limit: {limit}")
    
    try:
        # Import GroupMessage here to avoid circular imports
        from app.models.group_message import GroupMessage
        
        # Calculate skip value for pagination
        skip_count = (page - 1) * limit
        
        # Get messages for the group
        query = {
            "group_id": ObjectId(group_id),
            "is_deleted": False
        }
        
        # Get total count for this group to determine hasMore later
        total_messages_in_group = mongo.db.group_messages.count_documents(query)
        
        # Get messages, sorted newest first, then apply skip and limit
        messages_cursor = mongo.db.group_messages \
                        .find(query) \
                        .sort("created_at", -1) \
                        .skip(skip_count) \
                        .limit(limit)
        
        paginated_messages = list(messages_cursor)
        
        print(f"[GROUP API ROUTE] Found {len(paginated_messages)} messages after skip/limit. Total in group: {total_messages_in_group}")
        
        # Determine if there are more messages
        has_more = (skip_count + len(paginated_messages)) < total_messages_in_group
        
        # Debug: Print the first few messages if any
        if paginated_messages:
            print(f"[GROUP API ROUTE] First message of page: {paginated_messages[0]}")
        
        # Format messages for API response
        formatted_messages = []
        for msg_dict in reversed(paginated_messages): # Reverse to send oldest first for the current page
            # Fetch sender details to include sender_name and sender_avatar
            sender_info = User.get_by_id(msg_dict["sender_id"])
            sender_name = sender_info.get("username") if sender_info else "User"
            sender_avatar = sender_info.get("profile_picture") if sender_info else None

            # Get the attachment object/null from the DB record
            attachment_obj = msg_dict.get("attachment")

            formatted_message = {
                "id": str(msg_dict["_id"]),
                "group_id": str(msg_dict["group_id"]),
                "sender": str(msg_dict["sender_id"]),
                "content": msg_dict["content"],
                "timestamp": msg_dict["created_at"].isoformat() if isinstance(msg_dict["created_at"], datetime.datetime) else msg_dict["created_at"],
                "message_type": msg_dict.get("message_type", "text"),
                # Format as an array for the frontend
                "attachments": [attachment_obj] if attachment_obj else [], 
                "sender_name": sender_name,
                "sender_avatar": sender_avatar,
                "read_by": [str(user_id) for user_id in msg_dict.get("read_by", [])]
            }
            formatted_messages.append(formatted_message)
        
        print(f"[GROUP API ROUTE] Returning {len(formatted_messages)} formatted messages for page {page}")
        return jsonify({
            "success": True,
            "data": {
                "messages": formatted_messages,
                "hasMore": has_more
            }
        })
    except Exception as e:
        print(f"[GROUP API ROUTE] ❌ Unexpected error in route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Unexpected error retrieving group messages: {str(e)}"
        }), 500

@bp.route('/<group_id>/messages/<message_id>/read', methods=['POST'])
@jwt_required()
def mark_group_message_read(group_id, message_id):
    """Mark a group message as read by the current user"""
    current_user_id = get_jwt_identity()
    
    # Check if user is a member of the group
    group = Group.get_by_id(group_id)
    if not group:
        return jsonify({"success": False, "message": "Group not found"}), 404
    
    if ObjectId(current_user_id) not in group['members']:
        return jsonify({"success": False, "message": "You are not a member of this group"}), 403
    
    try:
        # Import GroupMessage here to avoid circular imports
        from app.models.group_message import GroupMessage
        
        # Mark the message as read
        success = GroupMessage.mark_read(message_id, current_user_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Message marked as read"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Message not found or already read"
            }), 404
    except Exception as e:
        print(f"Error marking group message as read: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error marking message as read: {str(e)}"
        }), 500

@bp.route('/<group_id>/messages/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_group_messages_read(group_id):
    """Mark all messages in a group as read by the current user"""
    current_user_id = get_jwt_identity()
    
    # Check if user is a member of the group
    group = Group.get_by_id(group_id)
    if not group:
        return jsonify({"success": False, "message": "Group not found"}), 404
    
    if ObjectId(current_user_id) not in group['members']:
        return jsonify({"success": False, "message": "You are not a member of this group"}), 403
    
    try:
        # Import GroupMessage here to avoid circular imports
        from app.models.group_message import GroupMessage
        
        # Mark all messages as read
        count = GroupMessage.mark_all_read(group_id, current_user_id)
        
        return jsonify({
            "success": True,
            "message": f"Marked {count} messages as read"
        })
    except Exception as e:
        print(f"Error marking all group messages as read: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error marking messages as read: {str(e)}"
        }), 500 
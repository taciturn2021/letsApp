from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from app.models.message import Message
from app.models.user import User
from app.models.group import Group
from app.models.group_message import GroupMessage
from app import mongo
import datetime

bp = Blueprint('messages', __name__)

@bp.route('/sync', methods=['GET'])
@jwt_required()
def sync_messages():
    """
    Sync all messages related to the current user.
    This endpoint retrieves all conversations (direct messages and group chats)
    and returns them formatted for the client.
    """
    current_user_id = get_jwt_identity()
    
    # Get all direct message conversations
    direct_conversations = get_direct_conversations(current_user_id)
    
    # Get all group conversations
    # group_conversations = get_group_conversations(current_user_id)
    
    return jsonify({
        "success": True,
        "data": {
            "direct_conversations": direct_conversations
            # "group_conversations": group_conversations
        }
    })

@bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_messages_with_user(user_id):
    """Get messages between current user and specified user with pagination"""
    current_user_id = get_jwt_identity()
    # Use the page/limit provided by the client, defaulting to 1 and 20 if not present
    page = request.args.get('page', 1, type=int) 
    limit = request.args.get('limit', 20, type=int)
    
    print(f"\n[API ROUTE] Getting messages between {current_user_id} and {user_id}")
    print(f"[API ROUTE] Page: {page}, Limit: {limit}")
    
    try:
        # Call the updated model method
        conversation_data = Message.get_conversation(current_user_id, user_id, page=page, limit=limit)
        
        # Check for errors from the model method if it returns dict with 'error'
        if 'error' in conversation_data:
            print(f"[API ROUTE] ❌ Error from Message.get_conversation: {conversation_data['error']}")
            return jsonify({
                "success": False,
                "message": f"Error retrieving messages: {conversation_data['error']}"
            }), 500

        messages_page = conversation_data.get("messages", [])
        has_more = conversation_data.get("hasMore", False)
        
        print(f"[API ROUTE] Model returned {len(messages_page)} messages. HasMore: {has_more}")
        
        # Format messages for API response (sender_name, sender_avatar should be added here ideally)
        formatted_messages = []
        for msg_dict in messages_page: # msg_dict is already a dictionary from the model
            # Fetch sender details to include sender_name and sender_avatar
            # This could be optimized by fetching sender details in bulk if performance is an issue
            sender_info = User.get_by_id(msg_dict["sender_id"])
            sender_name = sender_info.get("username") if sender_info else "User"
            sender_avatar = sender_info.get("profile_picture") if sender_info else None

            # Get the attachment object/null from the DB record
            attachment_obj = msg_dict.get("attachment")

            formatted_message = {
                "id": str(msg_dict["_id"]),
                "sender": str(msg_dict["sender_id"]),
                "recipient": str(msg_dict["recipient_id"]),
                "content": msg_dict["content"],
                "timestamp": msg_dict["created_at"].isoformat() if isinstance(msg_dict["created_at"], datetime.datetime) else msg_dict["created_at"],
                "status": msg_dict["status"],
                "message_type": msg_dict.get("message_type", "text"),
                # Format as an array for the frontend
                "attachments": [attachment_obj] if attachment_obj else [], 
                "sender_name": sender_name,
                "sender_avatar": sender_avatar
            }
            formatted_messages.append(formatted_message)
        
        print(f"[API ROUTE] Returning {len(formatted_messages)} formatted messages for page {page}")
        return jsonify({
            "success": True,
            "data": {
                "messages": formatted_messages,
                "hasMore": has_more
            }
        })
    except Exception as e:
        print(f"[API ROUTE] ❌ Unexpected error in route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Unexpected error retrieving messages: {str(e)}"
        }), 500

@bp.route('/<recipient_id>', methods=['POST'])
@jwt_required()
def send_message(recipient_id):
    """Send a message to a user with proper attachment handling"""
    current_user_id = get_jwt_identity()
    data = request.json
    
    print(f"\n[API] Sending message from {current_user_id} to {recipient_id}")
    print(f"[API] Message data: {data}")
    
    content = data.get('content', '')
    message_type = data.get('message_type', 'text')
    
    # Process attachment if present
    attachment = None
    if data.get('attachment'):
        attachment_data = data.get('attachment')
        
        # Ensure we have a valid file_id
        if attachment_data.get('file_id') and attachment_data.get('file_id') != 'undefined':
            attachment = attachment_data
            print(f"[API] Using attachment with file_id: {attachment_data.get('file_id')}")
            
            # If message type is not set, derive it from attachment type
            if message_type == 'text' and attachment_data.get('file_type'):
                message_type = attachment_data.get('file_type')
        else:
            print(f"[API] Warning: Invalid file_id in attachment: {attachment_data.get('file_id')}")
    
    try:
        # Create the message
        message = Message.create(
            sender_id=current_user_id,
            recipient_id=recipient_id,
            content=content,
            message_type=message_type,
            attachment=attachment
        )
        
        # Format the response
        formatted_message = {
            "id": str(message["_id"]),
            "sender": str(message["sender_id"]),
            "recipient": str(message["recipient_id"]),
            "content": message["content"],
            "timestamp": message["created_at"].isoformat(),
            "status": message["status"],
            "message_type": message.get("message_type", "text"),
            "attachment": message.get("attachment")
        }
        
        # Emit a socket.io event to notify the recipient about the new message
        from flask_socketio import emit
        from app.realtime.events import connected_users
        
        room_id = f"{min(current_user_id, recipient_id)}_{max(current_user_id, recipient_id)}"
        
        if recipient_id in connected_users:
            try:
                # Get sender details
                sender = User.get_by_id(current_user_id)
                
                # Get the attachment object/null from the created message
                attachment_obj = message.get('attachment')

                # Emit the message to the room
                emit('receive_message', {
                    'id': str(message['_id']),
                    'sender': str(message['sender_id']),
                    'sender_name': sender.get('username', ''),
                    'sender_avatar': sender.get('profile_picture', ''),
                    'recipient': str(message['recipient_id']),
                    'content': message['content'],
                    'timestamp': message['created_at'].isoformat(),
                    'status': message['status'],
                    'message_type': message['message_type'],
                    # Format as an array for the frontend
                    'attachments': [attachment_obj] if attachment_obj else [] 
                }, room=f"user_{recipient_id}", namespace='/')
                
                print(f"[API] Message notification sent to socket room: user_{recipient_id}")
            except Exception as e:
                print(f"[API] Error emitting socket event: {str(e)}")
        
        print(f"[API] Message sent successfully with ID: {str(message['_id'])}")
        return jsonify({
            "success": True,
            "message": "Message sent successfully",
            "data": formatted_message
        })
    except Exception as e:
        print(f"[API] ❌ Error sending message: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error sending message: {str(e)}"
        }), 500

def get_direct_conversations(user_id):
    """
    Get all direct message conversations for a user.
    
    Returns an array where each item contains:
    - contact_id: ID of the other person in the conversation
    - contact_info: Basic info about the contact (name, avatar)
    - messages: Array of messages in the conversation
    """
    # Use aggregation pipeline to find all conversations
    pipeline = [
        # Match messages where the user is either sender or recipient
        {
            "$match": {
                "$or": [
                    {"sender_id": ObjectId(user_id)},
                    {"recipient_id": ObjectId(user_id)}
                ],
                "is_deleted": False
            }
        },
        # Sort by creation time
        {"$sort": {"created_at": 1}},
        # Group by room_id (conversation)
        {
            "$group": {
                "_id": "$room_id",
                "messages": {"$push": "$$ROOT"},
                "last_message_time": {"$max": "$created_at"}
            }
        },
        # Sort conversations by the latest message
        {"$sort": {"last_message_time": -1}}
    ]
    
    result = list(mongo.db.messages.aggregate(pipeline))
    conversations = []
    
    for conversation in result:
        # Get the first message to determine who is the other person in this conversation
        if not conversation["messages"]:
            continue
            
        sample_message = conversation["messages"][0]
        contact_id = str(sample_message["sender_id"]) if str(sample_message["sender_id"]) != user_id else str(sample_message["recipient_id"])
        
        # Get contact information
        contact = User.get_by_id(contact_id)
        if not contact:
            continue
            
        contact_info = {
            "user_id": contact_id,
            "username": contact.get("username", ""),
            "full_name": contact.get("full_name", ""),
            "profile_picture": contact.get("profile_picture", "")
        }
        
        # Format messages
        formatted_messages = []
        for msg in conversation["messages"]:
            sender = User.get_by_id(str(msg["sender_id"]))
            if not sender:
                continue
                
            formatted_messages.append({
                "id": str(msg["_id"]),
                "sender": str(msg["sender_id"]),
                "sender_name": sender.get("username", ""),
                "sender_avatar": sender.get("profile_picture", ""),
                "recipient": str(msg["recipient_id"]),
                "content": msg["content"],
                "message_type": msg.get("message_type", "text"),
                "attachment": msg.get("attachment"),
                "timestamp": msg["created_at"].isoformat(),
                "status": msg["status"]
            })
        
        conversations.append({
            "contact_id": contact_id,
            "contact_info": contact_info,
            "last_message_time": conversation["last_message_time"].isoformat(),
            "messages": formatted_messages
        })
    
    return conversations

def get_group_conversations(user_id):
    """
    Get all group conversations for a user.
    
    Returns an array where each item contains:
    - group_id: ID of the group
    - group_info: Information about the group (name, description, etc.)
    - messages: Array of messages in the group
    """
    # First, get all groups the user is a member of
    user_groups = Group.get_user_groups(user_id)
    group_conversations = []
    
    for group in user_groups:
        group_id = str(group["_id"])
        
        # Get messages for the group
        messages = GroupMessage.get_messages(group_id)
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            sender = User.get_by_id(str(msg["sender_id"]))
            if not sender:
                continue
                
            formatted_messages.append({
                "id": str(msg["_id"]),
                "group_id": str(msg["group_id"]),
                "sender": str(msg["sender_id"]),
                "sender_name": sender.get("username", ""),
                "sender_avatar": sender.get("profile_picture", ""),
                "content": msg["content"],
                "message_type": msg.get("message_type", "text"),
                "attachment": msg.get("attachment"),
                "timestamp": msg["created_at"].isoformat(),
                "read_by": [str(user_id) for user_id in msg.get("read_by", [])]
            })
        
        # Format group info
        group_info = {
            "name": group.get("name", ""),
            "description": group.get("description", ""),
            "image": group.get("image", ""),
            "created_at": group.get("created_at").isoformat() if group.get("created_at") else None,
            "updated_at": group.get("updated_at").isoformat() if group.get("updated_at") else None,
            "members_count": len(group.get("members", [])),
            "is_admin": user_id in [str(admin_id) for admin_id in group.get("admins", [])]
        }
        
        # Calculate last message timestamp
        last_message_time = group.get("updated_at")
        if formatted_messages:
            # Parse the ISO timestamp back to a datetime object for comparison
            for msg in formatted_messages:
                msg_time = datetime.datetime.fromisoformat(msg["timestamp"].replace('Z', '+00:00'))
                if not last_message_time or msg_time > last_message_time:
                    last_message_time = msg_time
        
        group_conversations.append({
            "group_id": group_id,
            "group_info": group_info,
            "last_message_time": last_message_time.isoformat() if last_message_time else None,
            "messages": formatted_messages
        })
    
    # Sort by last message time (most recent first)
    group_conversations.sort(
        key=lambda x: x.get("last_message_time") or "1970-01-01T00:00:00", 
        reverse=True
    )
    
    return group_conversations
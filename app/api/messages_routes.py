from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from app.models.message import Message
from app.models.user import User
from app.models.group import Group
from app.models.group_message import GroupMessage
from app import mongo

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
            import datetime
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
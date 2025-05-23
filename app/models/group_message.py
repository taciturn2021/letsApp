import datetime
from bson import ObjectId
from app import mongo

class GroupMessage:
    """Group message model for group chat messages."""
    
    @staticmethod
    def create(group_id, sender_id, content, message_type="text", attachment=None):
        """
        Create a new group message
        
        Parameters:
        - group_id: ID of the group
        - sender_id: ID of the user sending the message
        - content: Message text content
        - message_type: Type of message (text, image, audio, video, document)
        - attachment: Optional file attachment details
        """
        message = {
            "group_id": ObjectId(group_id),
            "sender_id": ObjectId(sender_id),
            "content": content,
            "message_type": message_type,
            "attachment": attachment,
            "created_at": datetime.datetime.now(timezone.utc),
            "updated_at": datetime.datetime.now(timezone.utc),
            "read_by": [ObjectId(sender_id)],  # Sender automatically marks as read
            "is_deleted": False
        }
        
        result = mongo.db.group_messages.insert_one(message)
        message["_id"] = result.inserted_id
        
        # Update the group's updated_at timestamp
        mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$set": {"updated_at": datetime.datetime.now(timezone.utc)}}
        )
        
        return message
    
    @staticmethod
    def get_by_id(message_id):
        """Get group message by ID"""
        return mongo.db.group_messages.find_one({"_id": ObjectId(message_id), "is_deleted": False})
    
    @staticmethod
    def get_messages(group_id, limit=20, before_timestamp=None):
        """Get messages for a group with pagination"""
        query = {
            "group_id": ObjectId(group_id),
            "is_deleted": False
        }
        
        # Add timestamp filter if provided
        if before_timestamp:
            query["created_at"] = {"$lt": before_timestamp}
        
        # Get messages
        messages = list(mongo.db.group_messages
                       .find(query)
                       .sort("created_at", -1)
                       .limit(limit))
        
        # Return in reverse order (oldest first)
        return list(reversed(messages))
    
    @staticmethod
    def mark_read(message_id, user_id):
        """Mark message as read by a user"""
        result = mongo.db.group_messages.update_one(
            {"_id": ObjectId(message_id)},
            {
                "$addToSet": {"read_by": ObjectId(user_id)},
                "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    def mark_all_read(group_id, user_id):
        """Mark all messages in a group as read by a user"""
        result = mongo.db.group_messages.update_many(
            {
                "group_id": ObjectId(group_id),
                "is_deleted": False,
                "read_by": {"$ne": ObjectId(user_id)}
            },
            {
                "$addToSet": {"read_by": ObjectId(user_id)},
                "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
            }
        )
        return result.modified_count
    
    @staticmethod
    def delete(message_id, user_id):
        """Soft delete a message (only the sender or admin can delete)"""
        message = GroupMessage.get_by_id(message_id)
        
        if not message:
            return False
        
        # Check if user is the sender or an admin of the group
        group = mongo.db.groups.find_one({"_id": message["group_id"]})
        
        if (ObjectId(user_id) == message["sender_id"] or 
            (group and ObjectId(user_id) in group.get("admins", []))):
            
            result = mongo.db.group_messages.update_one(
                {"_id": ObjectId(message_id)},
                {
                    "$set": {
                        "is_deleted": True,
                        "updated_at": datetime.datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        
        return False

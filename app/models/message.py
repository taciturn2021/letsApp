import datetime
from bson import ObjectId
from app import mongo

class Message:
    """Message model for user-to-user communication."""
    
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"
    
    @staticmethod
    def create(sender_id, recipient_id, content, message_type="text", attachment=None):
        """
        Create a new message
        
        Parameters:
        - sender_id: ID of the user sending the message
        - recipient_id: ID of the user receiving the message
        - content: Message text content
        - message_type: Type of message (text, image, audio, video, document)
        - attachment: Optional file attachment details (for non-text messages)
        """
        message = {
            "sender_id": ObjectId(sender_id),
            "recipient_id": ObjectId(recipient_id),
            "content": content,
            "message_type": message_type,
            "attachment": attachment,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "status": Message.STATUS_SENT,
            "is_deleted": False,
            "room_id" : f"{min(sender_id, recipient_id)}_{max(sender_id, recipient_id)}",  # Generate a consistent room ID for the message
        }
        
        result = mongo.db.messages.insert_one(message)
        message["_id"] = result.inserted_id
        return message
    
    @staticmethod
    def get_by_id(message_id):
        """Get message by ID"""
        return mongo.db.messages.find_one({"_id": ObjectId(message_id), "is_deleted": False})
    
    @staticmethod
    def get_conversation(user1_id, user2_id, limit=20, before_timestamp=None):
        """Get messages between two users with pagination"""
        query = {
            "$or": [
                {"sender_id": ObjectId(user1_id), "recipient_id": ObjectId(user2_id)},
                {"sender_id": ObjectId(user2_id), "recipient_id": ObjectId(user1_id)}
            ],
            "is_deleted": False
        }
        
        # Add timestamp filter if provided
        if before_timestamp:
            query["created_at"] = {"$lt": before_timestamp}
        
        # Get messages
        messages = list(mongo.db.messages
                        .find(query)
                        .sort("created_at", -1)
                        .limit(limit))
        
        # Return in reverse order (oldest first)
        return list(reversed(messages))
    
    @staticmethod
    def update_status(message_id, status):
        """Update message status (sent, delivered, read)"""
        result = mongo.db.messages.update_one(
            {"_id": ObjectId(message_id)},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    def mark_delivered(user_id, sender_id):
        """Mark all messages from sender as delivered for recipient"""
        result = mongo.db.messages.update_many(
            {
                "sender_id": ObjectId(sender_id), 
                "recipient_id": ObjectId(user_id),
                "status": Message.STATUS_SENT
            },
            {
                "$set": {
                    "status": Message.STATUS_DELIVERED,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return result.modified_count
    
    @staticmethod
    def mark_read(user_id, sender_id):
        """Mark all messages from sender as read for recipient"""
        result = mongo.db.messages.update_many(
            {
                "sender_id": ObjectId(sender_id), 
                "recipient_id": ObjectId(user_id),
                "status": {"$ne": Message.STATUS_READ}
            },
            {
                "$set": {
                    "status": Message.STATUS_READ,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return result.modified_count
    
    @staticmethod
    def delete(message_id, user_id):
        """Soft delete a message (only the sender can delete)"""
        result = mongo.db.messages.update_one(
            {"_id": ObjectId(message_id), "sender_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

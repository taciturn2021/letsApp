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

        print(f"\n[MESSAGE CREATE] Attempting to create message from {sender_id} to {recipient_id}")
        print(f"[MESSAGE CREATE] Content: {content}")
        print(f"[MESSAGE CREATE] Type: {message_type}, Attachment: {attachment}")
        
        try:
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
            
            print(f"[MESSAGE CREATE] Inserting into database: {message}")
            result = mongo.db.messages.insert_one(message)
            print(f"[MESSAGE CREATE] Insert result: {result.inserted_id}")
            message["_id"] = result.inserted_id
            
            # Verify the message was actually saved
            saved_message = mongo.db.messages.find_one({"_id": result.inserted_id})
            if saved_message:
                print(f"[MESSAGE CREATE] Verification successful - message found in database")
            else:
                print(f"[MESSAGE CREATE] ⚠️ WARNING: Message not found in database after insert!")
                
            return message
        except Exception as e:
            print(f"[MESSAGE CREATE] ❌ ERROR: {str(e)}")
            raise
    
    @staticmethod
    def get_by_id(message_id):
        """Get message by ID"""
        return mongo.db.messages.find_one({"_id": ObjectId(message_id), "is_deleted": False})
    
    @staticmethod
    def get_conversation(user1_id, user2_id, limit=20, before_timestamp=None):
        """Get messages between two users with pagination"""
        print(f"\n[MESSAGE GET] Retrieving conversation between {user1_id} and {user2_id}")
        print(f"[MESSAGE GET] Limit: {limit}, Before timestamp: {before_timestamp}")
        
        try:
            query = {
                "$or": [
                    {"sender_id": ObjectId(user1_id), "recipient_id": ObjectId(user2_id)},
                    {"sender_id": ObjectId(user2_id), "recipient_id": ObjectId(user1_id)}
                ],
                "is_deleted": False
            }
            
            print(f"[MESSAGE GET] Query: {query}")
            
            # Add timestamp filter if provided
            if before_timestamp:
                query["created_at"] = {"$lt": before_timestamp}
            
            # Get messages
            messages = list(mongo.db.messages
                            .find(query)
                            .sort("created_at", -1)
                            .limit(limit))
            
            print(f"[MESSAGE GET] Found {len(messages)} messages")
            
            # Debug: Print the first few messages if any
            if messages:
                print(f"[MESSAGE GET] First message: {messages[0]}")
            else:
                # Check if collection exists and has any documents
                all_messages = list(mongo.db.messages.find().limit(1))
                print(f"[MESSAGE GET] Messages collection exists: {len(all_messages) > 0}")
                print(f"[MESSAGE GET] Total messages in database: {mongo.db.messages.count_documents({})}")
                
                # Check if room exists
                room_id = f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
                room_messages = list(mongo.db.messages.find({"room_id": room_id}).limit(1))
                print(f"[MESSAGE GET] Messages in room {room_id}: {len(room_messages)}")
            
            # Return in reverse order (oldest first)
            return list(reversed(messages))
        except Exception as e:
            print(f"[MESSAGE GET] ❌ ERROR: {str(e)}")
            raise
    
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

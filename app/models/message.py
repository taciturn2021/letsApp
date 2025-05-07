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
    def get_conversation(user1_id, user2_id, page=1, limit=20, before_timestamp=None):
        """Get messages between two users with pagination"""
        print(f"\n[MESSAGE GET] Retrieving conversation between {user1_id} and {user2_id}")
        print(f"[MESSAGE GET] Page: {page}, Limit: {limit}, Before timestamp: {before_timestamp}")
        
        try:
            query = {
                "$or": [
                    {"sender_id": ObjectId(user1_id), "recipient_id": ObjectId(user2_id)},
                    {"sender_id": ObjectId(user2_id), "recipient_id": ObjectId(user1_id)}
                ],
                "is_deleted": False
            }
            
            print(f"[MESSAGE GET] Query: {query}")
            
            # Add timestamp filter if provided (for cursor-based pagination, not strictly page-based here)
            # If using page-based, this 'before_timestamp' might be less relevant unless it's an anchor for the first page.
            # For simplicity with page/limit, we'll rely on skip and limit first.
            # if before_timestamp:
            #     query["created_at"] = {"$lt": before_timestamp}

            # Calculate skip value for pagination
            skip_count = (page - 1) * limit
            
            # Get messages, sorted newest first
            messages_cursor = mongo.db.messages \
                            .find(query) \
                            .sort("created_at", -1) 
            
            # Get total count for this conversation to determine hasMore later
            total_messages_in_conversation = mongo.db.messages.count_documents(query)

            # Apply skip and limit
            paginated_messages = list(messages_cursor.skip(skip_count).limit(limit))
            
            print(f"[MESSAGE GET] Found {len(paginated_messages)} messages after skip/limit. Total in convo: {total_messages_in_conversation}")
            
            # Determine if there are more messages
            # has_more = len(paginated_messages) == limit and (skip_count + len(paginated_messages)) < total_messages_in_conversation
            # A simpler way: if the number of messages on this page plus what we skipped is less than total, there's more.
            has_more = (skip_count + len(paginated_messages)) < total_messages_in_conversation

            # Debug: Print the first few messages if any
            if paginated_messages:
                print(f"[MESSAGE GET] First message of page: {paginated_messages[0]}")
            
            # Return messages for the current page (oldest first for this page) and hasMore flag
            return {
                "messages": list(reversed(paginated_messages)), # Reverse to send oldest first for the current page
                "hasMore": has_more
            }
        except Exception as e:
            print(f"[MESSAGE GET] ❌ ERROR: {str(e)}")
            # It's better to return a consistent structure or raise an error that the route can handle
            return {"messages": [], "hasMore": False, "error": str(e)} 
    
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

"""
AI Chat models for handling AI message storage and retrieval
"""
import uuid
from datetime import datetime
from bson import ObjectId
from app import mongo
import logging

logger = logging.getLogger(__name__)

class AIMessage:
    """Model for handling AI chat messages"""
    
    @staticmethod
    def create_user_message(user_id, room_id, content):
        """Create a user message document"""
        message = {
            "_id": str(uuid.uuid4()),
            "user_id": user_id,
            "room_id": room_id,
            "sender_id": user_id,
            "content": content,
            "timestamp": datetime.utcnow(),
            "message_type": "user",
            "is_ai_message": False,
            "status": "sent",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        return message
    
    @staticmethod
    def create_ai_message(user_id, room_id, content, ai_model="gemini-1.5-flash"):
        """Create an AI response message document"""
        message = {
            "_id": str(uuid.uuid4()),
            "user_id": user_id,
            "room_id": room_id,
            "sender_id": "ai-assistant",
            "content": content,
            "timestamp": datetime.utcnow(),
            "message_type": "ai",
            "is_ai_message": True,
            "ai_model": ai_model,
            "status": "delivered",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        return message
    
    @staticmethod
    def save_message(message):
        """Save a message to the database"""
        try:
            # Save to dedicated AI chat messages collection
            result = mongo.db.ai_chat_messages.insert_one(message)
            message["_id"] = str(result.inserted_id) if result.inserted_id else message["_id"]
            return message
        except Exception as e:
            logger.error(f"Failed to save AI message: {str(e)}")
            return None
    
    @staticmethod
    def get_chat_history(room_id, page=1, limit=50):
        """Get chat history for a room with pagination"""
        try:
            skip = (page - 1) * limit
            
            messages = list(mongo.db.ai_chat_messages.find(
                {"room_id": room_id}
            ).sort("timestamp", 1).skip(skip).limit(limit))
            
            # Convert ObjectId to string and format for frontend
            formatted_messages = []
            for message in messages:
                formatted_message = {
                    "id": str(message["_id"]),
                    "sender_id": message["sender_id"],
                    "content": message["content"],
                    "timestamp": message["timestamp"].isoformat() if isinstance(message["timestamp"], datetime) else message["timestamp"],
                    "message_type": message.get("message_type", "user" if message["sender_id"] != "ai-assistant" else "ai"),
                    "created_at": message.get("created_at", message["timestamp"]).isoformat() if isinstance(message.get("created_at", message["timestamp"]), datetime) else message.get("created_at", message["timestamp"]),
                    "ai_model": message.get("ai_model", None)
                }
                formatted_messages.append(formatted_message)
            
            return formatted_messages
        except Exception as e:
            logger.error(f"Failed to get chat history for room {room_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_total_messages_count(room_id):
        """Get total count of messages in a room"""
        try:
            return mongo.db.ai_chat_messages.count_documents({"room_id": room_id})
        except Exception as e:
            logger.error(f"Failed to get message count for room {room_id}: {str(e)}")
            return 0
    
    @staticmethod
    def get_conversation_context(user_id, room_id, limit=10):
        """Get recent conversation context for AI model"""
        try:
            messages = list(mongo.db.ai_chat_messages.find(
                {"user_id": user_id, "room_id": room_id}
            ).sort("timestamp", -1).limit(limit))
            
            # Build conversation context for AI
            conversation = []
            for msg in reversed(messages):
                if msg['message_type'] == 'user':
                    conversation.append({"role": "user", "content": msg['content']})
                else:
                    conversation.append({"role": "assistant", "content": msg['content']})
            
            return conversation
        except Exception as e:
            logger.error(f"Failed to get conversation context: {str(e)}")
            return []
    
    @staticmethod
    def clear_chat_history(user_id, room_id):
        """Clear all chat history for a user's room"""
        try:
            result = mongo.db.ai_chat_messages.delete_many(
                {"user_id": user_id, "room_id": room_id}
            )
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to clear chat history: {str(e)}")
            return 0

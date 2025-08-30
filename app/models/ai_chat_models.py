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
            "room_id": room_id,
            "sender_id": user_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "text",
            "is_ai_message": False,
            "status": "sent"
        }
        return message
    
    @staticmethod
    def create_ai_message(user_id, room_id, content, ai_model="gpt-3.5-turbo"):
        """Create an AI response message document"""
        message = {
            "_id": str(uuid.uuid4()),
            "room_id": room_id,
            "sender_id": "ai-assistant",
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "text",
            "is_ai_message": True,
            "ai_model": ai_model,
            "status": "delivered"
        }
        return message
    
    @staticmethod
    def save_message(message):
        """Save a message to the database"""
        try:
            result = mongo.db.messages.insert_one(message)
            message["_id"] = str(result.inserted_id) if result.inserted_id else message["_id"]
            return message
        except Exception as e:
            logger.error(f"Failed to save message: {str(e)}")
            return None
    
    @staticmethod
    def get_chat_history(room_id, limit=50):
        """Get chat history for a room"""
        try:
            messages = list(mongo.db.messages.find(
                {"room_id": room_id}
            ).sort("timestamp", 1).limit(limit))
            
            # Convert ObjectId to string for JSON serialization
            for message in messages:
                if isinstance(message["_id"], ObjectId):
                    message["_id"] = str(message["_id"])
                message["id"] = message["_id"]  # Frontend expects 'id' field
            
            return messages
        except Exception as e:
            logger.error(f"Failed to get chat history for room {room_id}: {str(e)}")
            return []

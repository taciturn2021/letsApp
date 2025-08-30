"""
AI Chat routes for LetsApp
Handles AI message sending, receiving, and chat history
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import logging
from app.models.user import User
from app.models.ai_chat_models import AIMessage
from app.utils.encryption import EncryptionManager

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
ai_chat_bp = Blueprint('ai_chat', __name__)

# Request validation schema
class AIMessageSchema(Schema):
    message = fields.Str(required=True, validate=fields.Length(min=1, max=4000))
    room_id = fields.Str(required=True)
    user_id = fields.Str(required=True)

ai_message_schema = AIMessageSchema()

@ai_chat_bp.route('/send', methods=['POST'])
@jwt_required()
def send_ai_message():
    """Send message to AI and get response"""
    try:
        # Get current user from JWT
        current_user_id = get_jwt_identity()
        logger.info(f"AI chat request from user {current_user_id}")
        
        # Validate request data
        try:
            data = ai_message_schema.load(request.json)
        except ValidationError as err:
            logger.warning(f"Validation error: {err.messages}")
            return jsonify({
                "success": False,
                "error": "Invalid request data",
                "details": err.messages
            }), 400
        
        user_message_content = data["message"]
        room_id = data["room_id"]
        user_id = data["user_id"]
        
        # Authorization check - user can only send messages as themselves
        if current_user_id != user_id:
            logger.warning(f"Authorization failed: {current_user_id} tried to send as {user_id}")
            return jsonify({
                "success": False,
                "error": "Unauthorized access"
            }), 403
        
        # Verify user exists
        user = User.get_by_id(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 404
        
        # Get user's API key
        user_api_key = User.get_api_key(user_id)
        if not user_api_key:
            logger.warning(f"No API key found for user {user_id}")
            return jsonify({
                "success": False,
                "error": "No API key configured. Please add your Google Gemini API key in profile settings."
            }), 400
        
        # Create and save user message
        user_message = AIMessage.create_user_message(user_id, room_id, user_message_content)
        saved_user_message = AIMessage.save_message(user_message)
        
        if not saved_user_message:
            logger.error("Failed to save user message")
            return jsonify({
                "success": False,
                "error": "Failed to save message"
            }), 500
        
        # Call Google Gemini API
        try:
            ai_response_content = get_gemini_response(user_api_key, user_message_content)
        except google_exceptions.PermissionDenied as e:
            logger.error(f"Google Gemini permission denied for user {user_id}: {str(e)}")
            return jsonify({
                "success": False,
                "error": "Invalid API key. Please check your Google Gemini API key in profile settings."
            }), 400
        except google_exceptions.ResourceExhausted as e:
            logger.error(f"Google Gemini rate limit exceeded for user {user_id}: {str(e)}")
            return jsonify({
                "success": False,
                "error": "API rate limit exceeded. Please try again later."
            }), 429
        except google_exceptions.GoogleAPICallError as e:
            logger.error(f"Google Gemini API call error for user {user_id}: {str(e)}")
            return jsonify({
                "success": False,
                "error": "AI service temporarily unavailable. Please try again later."
            }), 503
        except Exception as e:
            logger.error(f"Unexpected Google Gemini error for user {user_id}: {str(e)}")
            return jsonify({
                "success": False,
                "error": "AI service temporarily unavailable. Please try again later."
            }), 503
        
        # Create and save AI response message
        ai_message = AIMessage.create_ai_message(user_id, room_id, ai_response_content, ai_model="gemini-1.5-flash")
        saved_ai_message = AIMessage.save_message(ai_message)
        
        if not saved_ai_message:
            logger.error("Failed to save AI message")
            return jsonify({
                "success": False,
                "error": "Failed to save AI response"
            }), 500
        
        # Format response for frontend
        response_data = {
            "success": True,
            "user_message": {
                "id": saved_user_message["_id"],
                "content": saved_user_message["content"],
                "timestamp": saved_user_message["timestamp"],
                "sender_id": saved_user_message["sender_id"]
            },
            "ai_message": {
                "id": saved_ai_message["_id"],
                "content": saved_ai_message["content"],
                "timestamp": saved_ai_message["timestamp"],
                "sender_id": saved_ai_message["sender_id"]
            }
        }
        
        logger.info(f"AI chat response sent to user {user_id}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in AI chat: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500

@ai_chat_bp.route('/history/<room_id>', methods=['GET'])
@jwt_required()
def get_ai_chat_history(room_id):
    """Get AI chat history for a room"""
    try:
        current_user_id = get_jwt_identity()
        
        # Basic authorization - ensure user is accessing their own AI chat
        expected_room_id = f"ai_chat_{current_user_id}"
        if room_id != expected_room_id:
            logger.warning(f"Unauthorized room access: {current_user_id} tried to access {room_id}")
            return jsonify({
                "success": False,
                "error": "Unauthorized access to room"
            }), 403
        
        # Get chat history
        messages = AIMessage.get_chat_history(room_id)
        
        return jsonify({
            "success": True,
            "messages": messages
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting AI chat history: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to retrieve chat history"
        }), 500

def get_gemini_response(api_key, user_message):
    """Get response from Google Gemini API"""
    try:
        # Configure the Gemini API client
        genai.configure(api_key=api_key)
        
        # Create the generative model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Generate content
        response = model.generate_content(user_message)
        
        # Extract the text from the response
        ai_response = response.text
        return ai_response
        
    except Exception as e:
        logger.error(f"Google Gemini API call failed: {str(e)}")
        # Re-raise the exception to be handled by the main function
        raise

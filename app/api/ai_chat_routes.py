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
        
        # Get conversation context BEFORE saving the current message
        conversation_context = AIMessage.get_conversation_context(user_id, room_id, limit=10)
        logger.info(f"Retrieved {len(conversation_context)} context messages for user {user_id}")
        
        # Create and save user message
        user_message = AIMessage.create_user_message(user_id, room_id, user_message_content)
        saved_user_message = AIMessage.save_message(user_message)
        
        if not saved_user_message:
            logger.error("Failed to save user message")
            return jsonify({
                "success": False,
                "error": "Failed to save message"
            }), 500
        
        # Call Google Gemini API with conversation context
        try:
            ai_response_content = get_gemini_response(user_api_key, user_message_content, conversation_context)
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

@ai_chat_bp.route('/history/<user_id>', methods=['GET'])
@jwt_required()
def get_ai_chat_history(user_id):
    """Get AI chat history for a user with pagination"""
    try:
        current_user_id = get_jwt_identity()
        
        # Verify user can only access their own chat history
        if user_id != current_user_id:
            logger.warning(f"Unauthorized room access: {current_user_id} tried to access {user_id}")
            return jsonify({
                "success": False,
                "error": "Unauthorized to access this chat history"
            }), 403
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = min(int(request.args.get('limit', 50)), 100)  # Cap limit at 100
        
        # AI chat room format
        room_id = f"ai_chat_{user_id}"
        
        # Get chat history with pagination
        messages = AIMessage.get_chat_history(room_id, page, limit)
        
        # Get total count for pagination
        total_count = AIMessage.get_total_messages_count(room_id)
        
        # Calculate pagination info
        skip = (page - 1) * limit
        has_more = skip + len(messages) < total_count
        
        return jsonify({
            "success": True,
            "messages": messages,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "has_more": has_more
            }
        }), 200
        
    except ValueError as e:
        logger.warning(f"Invalid pagination parameters: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Invalid pagination parameters"
        }), 400
    except Exception as e:
        logger.error(f"Error getting AI chat history: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to retrieve chat history"
        }), 500

@ai_chat_bp.route('/history/<user_id>', methods=['DELETE'])
@jwt_required()
def clear_ai_chat_history(user_id):
    """Clear AI chat history for a user"""
    try:
        current_user_id = get_jwt_identity()
        
        # Verify user can only clear their own chat history
        if user_id != current_user_id:
            logger.warning(f"Unauthorized clear attempt: {current_user_id} tried to clear {user_id}")
            return jsonify({
                "success": False,
                "error": "Unauthorized to clear this chat history"
            }), 403
        
        # AI chat room format
        room_id = f"ai_chat_{user_id}"
        
        # Clear chat history
        deleted_count = AIMessage.clear_chat_history(user_id, room_id)
        
        logger.info(f"Cleared {deleted_count} AI chat messages for user {user_id}")
        
        return jsonify({
            "success": True,
            "message": f"Cleared {deleted_count} messages",
            "deleted_count": deleted_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error clearing AI chat history: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to clear chat history"
        }), 500

def get_gemini_response(api_key, user_message, conversation_context=None):
    """Get response from Google Gemini API with conversation context"""
    try:
        # Configure the Gemini API client
        genai.configure(api_key=api_key)
        
        # Define Leta AI persona
        system_prompt = """You are Leta AI, a helpful and friendly chatbot created specifically for the LetsApp messaging platform. 

Key traits:
- You are Leta AI, not Google's Gemini or any other AI
- You are designed to help users within the LetsApp messaging environment
- Be conversational, helpful, and engaging
- Keep responses concise but informative
- If asked about your identity, say "I am Leta AI, a chatbot implemented to help you in LetsApp"
- Don't mention Google, Gemini, or other AI systems
- Be friendly and approachable in your responses
- Help with general questions, conversations, and assistance

Remember: You are Leta AI, part of the LetsApp experience."""

        # Create the generative model with system instruction
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=system_prompt
        )
        
        # Build the conversation for context using Gemini's chat format
        if conversation_context and len(conversation_context) > 0:
            # Start a chat session with history
            chat = model.start_chat(history=[])
            
            # Add conversation history (last 10 messages)
            context_messages = conversation_context[-10:] if len(conversation_context) > 10 else conversation_context
            
            # Build chat history in pairs (user message -> assistant response)
            for i in range(0, len(context_messages), 2):
                if i < len(context_messages):
                    user_msg = context_messages[i]
                    if user_msg["role"] == "user":
                        # If there's a corresponding assistant response
                        if i + 1 < len(context_messages) and context_messages[i + 1]["role"] == "assistant":
                            assistant_msg = context_messages[i + 1]
                            # Add the pair to chat history
                            chat.history.extend([
                                {"role": "user", "parts": [user_msg["content"]]},
                                {"role": "model", "parts": [assistant_msg["content"]]}
                            ])
            
            # Send the current message
            response = chat.send_message(user_message)
        else:
            # No context, send message directly
            response = model.generate_content(user_message)
        
        # Extract the text from the response
        ai_response = response.text
        return ai_response
        
    except Exception as e:
        logger.error(f"Google Gemini API call failed: {str(e)}")
        # Re-raise the exception to be handled by the main function
        raise

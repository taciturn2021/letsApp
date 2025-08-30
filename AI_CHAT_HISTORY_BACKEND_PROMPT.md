# AI Chat History Backend Implementation Prompt

## Issue Description

The frontend AI chat needs to persist and reload previous chat messages, just like regular chats. Currently, AI chat messages are lost when the page refreshes or the chat is closed. We need to implement backend endpoints to store and retrieve AI chat history.

## Frontend Request Details

The frontend is making requests to:

- **GET** `/api/chat/ai/history/{userId}` - Get AI chat history for a user
- **POST** `/api/chat/ai/send` - Send AI message (needs to be updated to save messages)

## Required Backend Implementation

### 1. Database Schema for AI Chat Messages

```python
# MongoDB Collection: ai_chat_messages
{
    "_id": ObjectId,
    "user_id": String,  # ID of the user who owns this chat
    "room_id": String,  # AI chat room ID (format: "ai_chat_{user_id}")
    "sender_id": String,  # Either user_id or "ai-assistant"
    "content": String,  # Message content
    "timestamp": DateTime,
    "message_type": String,  # "user" or "ai"
    "ai_model": String,  # Which AI model was used (e.g., "gpt-3.5-turbo")
    "created_at": DateTime,
    "updated_at": DateTime
}
```

### 2. Update Existing AI Chat Send Endpoint

The existing `/api/chat/ai/send` endpoint needs to be updated to save both user messages and AI responses to the database.

```python
@ai_chat_bp.route('/api/chat/ai/send', methods=['POST'])
@jwt_required()
def send_ai_message():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()

        # Validate request data
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400

        user_message = data['message']
        room_id = data.get('room_id', f"ai_chat_{current_user_id}")
        user_id = data.get('user_id', current_user_id)

        # Verify user can only send messages for themselves
        if user_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Get user's API key from database
        user = User.find_by_id(current_user_id)
        if not user or not user.encrypted_api_key:
            return jsonify({'error': 'No API key found. Please add your OpenAI API key in settings.'}), 400

        # Decrypt API key
        decrypted_api_key = user.get_decrypted_api_key()
        if not decrypted_api_key:
            return jsonify({'error': 'Invalid API key. Please update your API key in settings.'}), 400

        # Save user message to database
        user_message_doc = {
            "user_id": current_user_id,
            "room_id": room_id,
            "sender_id": current_user_id,
            "content": user_message,
            "message_type": "user",
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        user_msg_result = db.ai_chat_messages.insert_one(user_message_doc)
        user_message_doc['_id'] = user_msg_result.inserted_id

        # Call OpenAI API
        try:
            openai.api_key = decrypted_api_key

            # Get conversation context (last 10 messages for context)
            previous_messages = list(db.ai_chat_messages.find(
                {"user_id": current_user_id, "room_id": room_id}
            ).sort("timestamp", -1).limit(20))

            # Build conversation context
            conversation = []
            for msg in reversed(previous_messages[:-1]):  # Exclude the just-added user message
                if msg['message_type'] == 'user':
                    conversation.append({"role": "user", "content": msg['content']})
                else:
                    conversation.append({"role": "assistant", "content": msg['content']})

            # Add current user message
            conversation.append({"role": "user", "content": user_message})

            # Make OpenAI API call
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Leta AI, a helpful personal assistant. Be friendly, concise, and helpful."},
                    *conversation
                ],
                max_tokens=1000,
                temperature=0.7
            )

            ai_response = response.choices[0].message.content

            # Save AI response to database
            ai_message_doc = {
                "user_id": current_user_id,
                "room_id": room_id,
                "sender_id": "ai-assistant",
                "content": ai_response,
                "message_type": "ai",
                "ai_model": "gpt-3.5-turbo",
                "timestamp": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            ai_msg_result = db.ai_chat_messages.insert_one(ai_message_doc)
            ai_message_doc['_id'] = ai_msg_result.inserted_id

            return jsonify({
                'success': True,
                'user_message': {
                    'id': str(user_message_doc['_id']),
                    'content': user_message_doc['content'],
                    'timestamp': user_message_doc['timestamp'].isoformat(),
                    'sender_id': user_message_doc['sender_id']
                },
                'ai_message': {
                    'id': str(ai_message_doc['_id']),
                    'content': ai_message_doc['content'],
                    'timestamp': ai_message_doc['timestamp'].isoformat(),
                    'sender_id': ai_message_doc['sender_id']
                }
            }), 200

        except Exception as openai_error:
            print(f"OpenAI API Error: {str(openai_error)}")

            # Save error response as AI message
            error_message = "I'm sorry, I'm having trouble processing your request right now. Please try again later."
            ai_error_doc = {
                "user_id": current_user_id,
                "room_id": room_id,
                "sender_id": "ai-assistant",
                "content": error_message,
                "message_type": "ai",
                "ai_model": "error",
                "timestamp": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            ai_error_result = db.ai_chat_messages.insert_one(ai_error_doc)
            ai_error_doc['_id'] = ai_error_result.inserted_id

            return jsonify({
                'success': True,
                'user_message': {
                    'id': str(user_message_doc['_id']),
                    'content': user_message_doc['content'],
                    'timestamp': user_message_doc['timestamp'].isoformat(),
                    'sender_id': user_message_doc['sender_id']
                },
                'ai_message': {
                    'id': str(ai_error_doc['_id']),
                    'content': ai_error_doc['content'],
                    'timestamp': ai_error_doc['timestamp'].isoformat(),
                    'sender_id': ai_error_doc['sender_id']
                }
            }), 200

    except Exception as e:
        print(f"Error in AI chat send: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
```

### 3. Create AI Chat History Endpoint

```python
@ai_chat_bp.route('/api/chat/ai/history/<user_id>', methods=['GET'])
@jwt_required()
def get_ai_chat_history(user_id):
    try:
        current_user_id = get_jwt_identity()

        # Verify user can only access their own chat history
        if user_id != current_user_id:
            return jsonify({'error': 'Unauthorized to access this chat history'}), 403

        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        skip = (page - 1) * limit

        # Get AI chat messages for this user
        room_id = f"ai_chat_{user_id}"

        messages = list(db.ai_chat_messages.find(
            {"user_id": user_id, "room_id": room_id}
        ).sort("timestamp", 1).skip(skip).limit(limit))

        # Format messages for frontend
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'id': str(msg['_id']),
                'sender_id': msg['sender_id'],
                'content': msg['content'],
                'timestamp': msg['timestamp'].isoformat(),
                'message_type': msg.get('message_type', 'user' if msg['sender_id'] != 'ai-assistant' else 'ai'),
                'created_at': msg['created_at'].isoformat() if 'created_at' in msg else msg['timestamp'].isoformat()
            })

        # Get total count for pagination
        total_count = db.ai_chat_messages.count_documents(
            {"user_id": user_id, "room_id": room_id}
        )

        return jsonify({
            'success': True,
            'messages': formatted_messages,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'has_more': skip + len(formatted_messages) < total_count
            }
        }), 200

    except Exception as e:
        print(f"Error getting AI chat history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
```

### 4. Optional: Clear AI Chat History Endpoint

```python
@ai_chat_bp.route('/api/chat/ai/history/<user_id>', methods=['DELETE'])
@jwt_required()
def clear_ai_chat_history(user_id):
    try:
        current_user_id = get_jwt_identity()

        # Verify user can only clear their own chat history
        if user_id != current_user_id:
            return jsonify({'error': 'Unauthorized to clear this chat history'}), 403

        # Delete all AI chat messages for this user
        room_id = f"ai_chat_{user_id}"
        result = db.ai_chat_messages.delete_many(
            {"user_id": user_id, "room_id": room_id}
        )

        return jsonify({
            'success': True,
            'message': f'Cleared {result.deleted_count} messages',
            'deleted_count': result.deleted_count
        }), 200

    except Exception as e:
        print(f"Error clearing AI chat history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
```

### 5. Register the Blueprint

```python
# In your main Flask app
from your_ai_chat_module import ai_chat_bp

app.register_blueprint(ai_chat_bp)
```

### 6. Required Dependencies

Make sure these are installed:

```bash
pip install openai pymongo flask-jwt-extended cryptography
```

### 7. Environment Variables

Add to your `.env` file:

```
OPENAI_API_KEY=your_fallback_api_key_here  # Optional fallback
API_KEY_ENCRYPTION_KEY=your_fernet_key_here
```

## Frontend Integration Notes

The frontend expects:

- **Success Response**: `{ success: true, messages: [...] }`
- **Error Response**: `{ success: false, error: "error message" }`
- **Message Format**: Each message should have `id`, `sender_id`, `content`, `timestamp`

## Testing

1. Test AI message sending and saving to database
2. Test AI chat history retrieval
3. Test pagination for long conversations
4. Test error handling for invalid API keys
5. Test conversation context (AI should remember previous messages)

## Security Considerations

- JWT authentication required for all endpoints
- Users can only access their own chat history
- API keys are encrypted in database
- Input validation for all requests
- Rate limiting recommended for AI endpoints

This implementation will provide persistent AI chat history that survives page refreshes and chat closures, just like regular chat messages.

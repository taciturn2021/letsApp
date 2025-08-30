# Backend API Key Management Fix Prompt

## Issue Description

The frontend is making API calls to save user API keys but receiving 400 BAD REQUEST errors. The API key save functionality was previously working but is now broken.

## Frontend Request Details

- **Endpoint**: `PUT /api/users/{userId}/api-key`
- **Request Body**: `{ "api_key": "user_provided_api_key" }`
- **Headers**: Authorization header with JWT token
- **Expected Response**: Success confirmation with updated user data

## Error Details

- **Status Code**: 400 BAD REQUEST
- **Frontend Error Log**: API key update failing
- **Previous State**: This endpoint was working before, something changed

## Required Backend Implementation

### 1. Create/Fix API Key Management Endpoint

```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from cryptography.fernet import Fernet
import os

api_key_bp = Blueprint('api_key', __name__)

# Encryption key for API keys (should be in environment variables)
ENCRYPTION_KEY = os.getenv('API_KEY_ENCRYPTION_KEY', Fernet.generate_key())
cipher_suite = Fernet(ENCRYPTION_KEY)

@api_key_bp.route('/api/users/<user_id>/api-key', methods=['PUT'])
@jwt_required()
def update_user_api_key(user_id):
    try:
        # Verify the user is updating their own API key
        current_user_id = get_jwt_identity()
        if current_user_id != user_id:
            return jsonify({'error': 'Unauthorized to update this user\'s API key'}), 403

        # Get the API key from request body
        data = request.get_json()
        if not data or 'api_key' not in data:
            return jsonify({'error': 'API key is required in request body'}), 400

        api_key = data['api_key']
        if not api_key or not isinstance(api_key, str):
            return jsonify({'error': 'Valid API key string is required'}), 400

        # Encrypt the API key
        encrypted_api_key = cipher_suite.encrypt(api_key.encode()).decode()

        # Update user's API key in database
        from your_db_module import db, User  # Import your database and User model

        user = User.find_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Update the user's encrypted API key
        user.encrypted_api_key = encrypted_api_key
        user.save()

        return jsonify({
            'message': 'API key updated successfully',
            'user_id': user_id
        }), 200

    except Exception as e:
        print(f"Error updating API key: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_key_bp.route('/api/users/<user_id>/api-key', methods=['GET'])
@jwt_required()
def get_user_api_key(user_id):
    try:
        # Verify the user is getting their own API key
        current_user_id = get_jwt_identity()
        if current_user_id != user_id:
            return jsonify({'error': 'Unauthorized to access this user\'s API key'}), 403

        # Get user from database
        from your_db_module import db, User

        user = User.find_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Check if user has an API key
        if not user.encrypted_api_key:
            return jsonify({'has_api_key': False}), 200

        # Decrypt the API key (only return existence, not the key itself for security)
        try:
            decrypted_key = cipher_suite.decrypt(user.encrypted_api_key.encode()).decode()
            return jsonify({
                'has_api_key': True,
                'api_key_preview': f"{decrypted_key[:8]}..." if len(decrypted_key) > 8 else "****"
            }), 200
        except:
            return jsonify({'has_api_key': False, 'error': 'Invalid encrypted key'}), 200

    except Exception as e:
        print(f"Error getting API key: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_key_bp.route('/api/users/<user_id>/api-key', methods=['DELETE'])
@jwt_required()
def delete_user_api_key(user_id):
    try:
        # Verify the user is deleting their own API key
        current_user_id = get_jwt_identity()
        if current_user_id != user_id:
            return jsonify({'error': 'Unauthorized to delete this user\'s API key'}), 403

        # Get user from database
        from your_db_module import db, User

        user = User.find_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Remove the API key
        user.encrypted_api_key = None
        user.save()

        return jsonify({'message': 'API key deleted successfully'}), 200

    except Exception as e:
        print(f"Error deleting API key: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
```

### 2. Update User Model

Ensure your User model has the encrypted_api_key field:

```python
# In your User model (MongoDB/SQLAlchemy/etc.)
class User:
    # ... other fields
    encrypted_api_key = None  # String field to store encrypted API key

    # Method to get decrypted API key for internal use
    def get_decrypted_api_key(self):
        if not self.encrypted_api_key:
            return None
        try:
            cipher_suite = Fernet(os.getenv('API_KEY_ENCRYPTION_KEY'))
            return cipher_suite.decrypt(self.encrypted_api_key.encode()).decode()
        except:
            return None
```

### 3. Register the Blueprint

In your main Flask app:

```python
from your_api_key_module import api_key_bp

app.register_blueprint(api_key_bp)
```

### 4. Environment Variables

Add to your `.env` file:

```
API_KEY_ENCRYPTION_KEY=your_generated_fernet_key_here
```

## Debugging Steps

1. Check if the route `/api/users/<user_id>/api-key` exists in your Flask app
2. Verify the route accepts PUT requests
3. Ensure JWT authentication is working
4. Check if the request body parsing is correct
5. Verify database connection and User model
6. Test with a simple endpoint first to isolate the issue

## Testing

After implementation, test with:

```bash
curl -X PUT http://localhost:5000/api/users/{user_id}/api-key \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {jwt_token}" \
  -d '{"api_key": "test_api_key"}'
```

## Error Handling Requirements

- Return 400 for invalid request body
- Return 401 for missing/invalid JWT
- Return 403 for unauthorized access to other user's API key
- Return 404 for user not found
- Return 500 for server errors
- Log all errors for debugging

Fix the backend to handle the API key update request properly and return appropriate responses to the frontend.

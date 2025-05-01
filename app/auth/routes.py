from flask import request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from app.auth import bp
from app.models.user import User
from app.models.presence import Presence
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError
from app.schemas.schema import UserRegistrationSchema, UserLoginSchema

# Create a limiter that will be properly configured when the app starts
limiter = Limiter(key_func=get_remote_address)

@bp.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """Register a new user"""
    data = request.get_json()
    schema = UserRegistrationSchema()
    
    try:
        validated_data = schema.load(data)
        
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    # Check if user already exists
    if User.get_by_email(data['email']):
        return jsonify({"error": "Email already registered"}), 409
    
    if User.get_by_username(data['username']):
        return jsonify({"error": "Username already taken"}), 409
    
    # Create user
    user = User.create(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        full_name=data.get('full_name')
    )
    
    # Generate tokens
    access_token = create_access_token(identity=str(user['_id']))
    refresh_token = create_refresh_token(identity=str(user['_id']))
    
    # Set user as online
    Presence.update_status(user['_id'], Presence.STATUS_ONLINE)
    
    return jsonify({
        "message": "User registered successfully",
        "user": {
            "id": str(user['_id']),
            "username": user['username'],
            "email": user['email']
        },
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 201

@bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """Log in a user"""
    data = request.get_json()
    schema = UserLoginSchema()
    
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400
    
    # Authenticate user
    user = User.authenticate(data['email'], data['password'])
    
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Generate tokens
    access_token = create_access_token(identity=str(user['_id']))
    refresh_token = create_refresh_token(identity=str(user['_id']))
    
    # Set user as online
    Presence.update_status(user['_id'], Presence.STATUS_ONLINE)
    
    return jsonify({
        "message": "Login successful",
        "user": {
            "id": str(user['_id']),
            "username": user['username'],
            "email": user['email']
        },
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 200

@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user = get_jwt_identity()
    access_token = create_access_token(identity=current_user)
    
    return jsonify({
        "message": "Token refreshed",
        "access_token": access_token
    }), 200

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Log out a user"""
    current_user = get_jwt_identity()
    
    # Set user as offline
    Presence.update_status(current_user, Presence.STATUS_OFFLINE)
    
    # Note: JWT cannot be invalidated without a blacklist/database
    # In a production app, you would add the token to a blacklist
    
    return jsonify({"message": "Logged out successfully"}), 200

@bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """Get current user profile"""
    current_user_id = get_jwt_identity()
    user = User.get_by_id(current_user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "id": str(user['_id']),
        "username": user['username'],
        "email": user['email'],
        "full_name": user.get('full_name'),
        "profile_picture": user.get('profile_picture'),
        "bio": user.get('bio', ''),
        "created_at": user['created_at'].isoformat(),
        "last_seen": user['last_seen'].isoformat()
    }), 200

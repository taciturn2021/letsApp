from flask import jsonify, request
from app.api import bp
from app.models import User, Message, Group, GroupMessage, Contact, File, Presence

@bp.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "API is running"})

@bp.route('/users', methods=['GET'])
def get_users():
    """Get all users (demonstration endpoint)"""
    users = list(User.get_all())
    # Remove passwords from the response
    for user in users:
        if 'password' in user:
            del user['password']
    return jsonify({"users": users})

@bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
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
    
    return jsonify({"user": user, "message": "User created successfully"}), 201

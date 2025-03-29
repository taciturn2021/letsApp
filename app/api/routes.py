from flask import jsonify, request , Blueprint
from app.api import bp
from app.models import User, Message, Group, GroupMessage, Contact, File, Presence


bp = Blueprint('load', __name__)

@bp.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "API is running"})

@bp.route('/all_users', methods=['GET'])
def get_users():
    """Get all users (demonstration endpoint)"""
    users = list(User.get_all())
    
    print(users)
    
    # Remove passwords from the response
    for user in users:
        if 'password' in user:
            del user['password']
    return jsonify({"users": users})



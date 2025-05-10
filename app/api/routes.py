from flask import jsonify, request , Blueprint
from app.api import bp
from app.models import User, Message, Group, GroupMessage, Contact, File, Presence
from app.models.presence import Presence


bp = Blueprint('load', __name__)

@bp.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "API is running"})

@bp.route('/all_users', methods=['GET'])
def get_users():
    """Get all users (demonstration endpoint)"""
    print(f"Request from host: {request.remote_addr}, port: {request.environ.get('REMOTE_PORT', 'unknown')}")
    users = list(User.get_all())
    
    # Remove passwords from the response and add presence data
    for user in users:
        if 'password' in user:
            del user['password']
        
        # Add presence status
        user_id = str(user.get('_id'))
        user['status'] = Presence.get_status(user_id)
        
    print(f"Returning {len(users)} users with presence status")
    return jsonify({"users": users})



from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.models.user import User
from app.models.group import Group
from bson import ObjectId

def admin_required(fn):
    """Decorator to check if user is an admin"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        
        # Check if user is an admin
        user = User.get_by_id(user_id)
        if not user or not user.get('is_admin', False):
            return jsonify({"error": "Admin privileges required"}), 403
        
        return fn(*args, **kwargs)
    
    return wrapper

def group_member_required(fn):
    """Decorator to check if user is a member of the specified group"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        
        # Get group_id from URL parameters or request JSON
        group_id = request.view_args.get('group_id')
        if not group_id and request.is_json:
            group_id = request.json.get('group_id')
            
        if not group_id:
            return jsonify({"error": "Group ID is required"}), 400
        
        # Check if user is a member of the group
        group = Group.get_by_id(group_id)
        if not group or ObjectId(user_id) not in group['members']:
            return jsonify({"error": "You are not a member of this group"}), 403
        
        return fn(*args, **kwargs)
    
    return wrapper

def group_admin_required(fn):
    """Decorator to check if user is an admin of the specified group"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        
        # Get group_id from URL parameters or request JSON
        group_id = request.view_args.get('group_id')
        if not group_id and request.is_json:
            group_id = request.json.get('group_id')
            
        if not group_id:
            return jsonify({"error": "Group ID is required"}), 400
        
        # Check if user is an admin of the group
        group = Group.get_by_id(group_id)
        if not group or ObjectId(user_id) not in group['admins']:
            return jsonify({"error": "You need admin privileges for this group"}), 403
        
        return fn(*args, **kwargs)
    
    return wrapper

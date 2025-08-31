from flask import Blueprint, request, jsonify, current_app, send_from_directory, url_for, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.models.user import User
from app.models.media import Media
from app.schemas.schema import UserProfileSchema, UserSettingsSchema, PasswordChangeSchema
from app.schemas.schema import PasswordResetRequestSchema, PasswordResetSchema, ApiKeySchema
from app.utils.file_handler import save_profile_picture
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

bp = Blueprint('users', __name__)
limiter = Limiter(key_func=get_remote_address)

# 1. User Profile Information Management

@bp.route('/<user_id>', methods=['GET'])
@jwt_required()
def get_user_profile(user_id):
    """Get user profile by ID"""
    current_user_id = get_jwt_identity()
    
    # If not requesting own profile, ensure minimal data is returned
    if current_user_id != user_id:
        user = User.get_by_id(user_id)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Return only public information for other users
        return jsonify({
            "success": True,
            "data": {
                "username": user.get("username"),
                "full_name": user.get("full_name"),
                "bio": user.get("bio", ""),
                "profile_picture": user.get("profile_picture"),
                "last_seen": user.get("last_seen").isoformat() if user.get("last_seen") else None
            }
        })
    
    # Return full profile data for own profile
    user = User.get_by_id(current_user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
        
    return jsonify({
        "success": True,
        "data": {
            "id": str(user.get("_id")),
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "bio": user.get("bio", ""),
            "profile_picture": user.get("profile_picture"),
            "last_seen": user.get("last_seen").isoformat() if user.get("last_seen") else None,
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
            "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None,
            "settings": user.get("settings", {
                "notifications_enabled": True,
                "read_receipts_enabled": True,
                "typing_indicators_enabled": True
            })
        }
    })

@bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
@limiter.limit("10 per minute")
def update_user_profile(user_id):
    """Update user profile including settings"""
    current_user_id = get_jwt_identity()
    
    # Ensure users can only update their own profile
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized to update this profile"}), 403
    
    data = request.get_json()
    
    # Validate profile data
    profile_data = {}
    settings_data = {}
    
    # Split data into profile and settings
    if "profile" in data:
        profile_schema = UserProfileSchema()
        try:
            profile_data = profile_schema.load(data["profile"])
        except ValidationError as err:
            return jsonify({"success": False, "errors": {"profile": err.messages}}), 400
    
    # Handle settings if provided
    if "settings" in data:
        settings_schema = UserSettingsSchema()
        try:
            settings_data = settings_schema.load(data["settings"])
        except ValidationError as err:
            return jsonify({"success": False, "errors": {"settings": err.messages}}), 400
    
    # Update profile if there's profile data
    if profile_data:
        profile_result = User.update_profile(current_user_id, profile_data)
        if not profile_result["success"]:
            return jsonify(profile_result), 400
    
    # Update settings if there's settings data
    if settings_data:
        settings_result = User.update_settings(current_user_id, settings_data)
        if not settings_result["success"]:
            return jsonify(settings_result), 400
    
    return jsonify({
        "success": True,
        "message": "Profile and settings updated successfully"
    }), 200

# 2. Profile Picture Management

@bp.route('/<user_id>/profile-picture', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def upload_profile_picture(user_id):
    """Upload a new profile picture"""
    current_user_id = get_jwt_identity()
    
    # Ensure users can only update their own profile picture
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized to update this profile"}), 403
    
    # Check if request has a file
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    
    file = request.files['file']
    
    # Handle the file upload - pass upload_folder for backward compatibility
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
    result = save_profile_picture(file, current_user_id, upload_folder)
    
    if not result["success"]:
        return jsonify(result), 400
    
    # Link the media to the user's profile
    update_result = User.update_profile_picture(current_user_id, result["media_id"])
    
    if update_result["success"]:
        # Return URLs for immediate use in frontend
        media_id = result["media_id"]
        return jsonify({
            "success": True, 
            "message": "Profile picture updated successfully",
            "media_id": media_id,
            "url": url_for('media.get_media_file', file_id=media_id, _external=True),
            "thumbnail_url": url_for('media.get_media_file', file_id=media_id, thumbnail='true', _external=True)
        }), 200
    else:
        return jsonify(update_result), 500

@bp.route('/<user_id>/profile-picture', methods=['DELETE'])
@jwt_required()
def delete_profile_picture(user_id):
    """Delete the user's profile picture"""
    current_user_id = get_jwt_identity()
    
    # Ensure users can only delete their own profile picture
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized to update this profile"}), 403
    
    # Get the current profile picture ID
    user = User.get_by_id(current_user_id)
    if not user or not user.get("profile_picture"):
        return jsonify({"success": False, "message": "No profile picture to delete"}), 404
    
    # First remove the reference from the user document
    result = User.remove_profile_picture(current_user_id)
    
    if not result["success"]:
        return jsonify(result), 500
    
    # Then mark the media as deleted
    # Note: For simplicity, we're not physically deleting the file, just marking it as deleted in the database
    # In a production application, you might want to clean up the files periodically
    try:
        Media.delete(user["profile_picture"], current_user_id)
    except Exception as e:
        # Log the error but don't fail the request
        print(f"Error deleting media: {str(e)}")
    
    return jsonify({"success": True, "message": "Profile picture deleted successfully"}), 200

@bp.route('/media/<media_id>', methods=['GET'])
def get_media(media_id):
    """Get media file (public route) - Redirects to the media_routes endpoint"""
    # This route is maintained for backward compatibility
    # Redirect to the more appropriate media endpoint
    use_thumbnail = request.args.get('thumbnail', 'false').lower() == 'true'
    
    # Construct the redirect URL to the media route
    redirect_url = url_for(
        'media.get_media_file', 
        file_id=media_id,
        thumbnail='true' if use_thumbnail else 'false',
        _external=True
    )
    
    return redirect(redirect_url)

# 4. Password Management

@bp.route('/<user_id>/change-password', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def change_password(user_id):
    """Change user password"""
    current_user_id = get_jwt_identity()
    
    # Ensure users can only change their own password
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized to change this password"}), 403
    
    data = request.get_json()
    schema = PasswordChangeSchema()
    
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
         return jsonify({"success": False, "message": "Password must be at least 6 characters long"}), 400
    
    # Change password
    result = User.change_password(
        current_user_id, 
        validated_data["current_password"], 
        validated_data["new_password"]
    )
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@bp.route('/forgot-password', methods=['POST'])
@limiter.limit("5 per minute")
def forgot_password():
    """Initiate password reset flow"""
    data = request.get_json()
    schema = PasswordResetRequestSchema()
    
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 400
    
    # Generate reset token
    result = User.generate_reset_token(validated_data["email"])
    
    # Always return 200 to prevent user enumeration
    return jsonify(result), 200

@bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    """Complete password reset with token"""
    data = request.get_json()
    schema = PasswordResetSchema()
    
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 400
    
    # Reset password
    result = User.reset_password(
        validated_data["token"],
        validated_data["new_password"]
    )
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

# 6. API Key Management

@bp.route('/<user_id>/api-key', methods=['PUT'])
@jwt_required()
def update_api_key(user_id):
    """Update user's API key with encryption"""
    current_user_id = get_jwt_identity()
    
    # Users can only update their own API key
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    data = request.get_json()
    schema = ApiKeySchema()
    
    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 400
    
    # Update the API key
    result = User.update_api_key(user_id, validated_data["api_key"])
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@bp.route('/<user_id>/api-key', methods=['GET'])
@jwt_required()
def get_api_key(user_id):
    """Get user's decrypted API key"""
    current_user_id = get_jwt_identity()
    
    # Users can only get their own API key
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    api_key = User.get_api_key(user_id)
    
    if api_key:
        return jsonify({
            "success": True,
            "data": {"api_key": api_key}
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": "No API key found. Please set your API key first.",
            "code": "NO_API_KEY"
        }), 404

@bp.route('/<user_id>/api-key', methods=['DELETE'])
@jwt_required()
def remove_api_key(user_id):
    """Remove user's API key"""
    current_user_id = get_jwt_identity()
    
    # Users can only remove their own API key
    if current_user_id != user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    result = User.remove_api_key(user_id)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400
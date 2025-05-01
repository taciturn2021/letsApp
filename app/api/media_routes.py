from flask import Blueprint, request, jsonify, send_file, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.models.media import Media
from app.models.file import File
from app.utils.file_handler import (
    save_file_to_gridfs, 
    get_file_from_gridfs,
    generate_signed_url,
    save_profile_picture,
    fs
)
from app.models.user import User
from bson import ObjectId
from gridfs.errors import NoFile
import io
import os

bp = Blueprint('media', __name__)
limiter = Limiter(key_func=get_remote_address)

def validate_token_param(token):
    """Validate JWT token from query parameter"""
    from flask_jwt_extended import decode_token
    try:
        decoded_token = decode_token(token)
        return decoded_token
    except Exception:
        return None

@bp.route('/upload', methods=['POST'])
@jwt_required()
@limiter.limit("20 per minute")
def upload_media():
    """Upload media file to GridFS"""
    current_user_id = get_jwt_identity()
    
    # Check if request has a file
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    
    file = request.files['file']
    file_type = request.form.get('type')  # Optional file type override
    message_id = request.form.get('message_id')  # Optional message reference
    group_message_id = request.form.get('group_message_id')  # Optional group message reference
    
    # Process and save the file
    result = save_file_to_gridfs(
        file, 
        current_user_id, 
        file_type=file_type, 
        message_id=message_id,
        group_message_id=group_message_id
    )
    
    if not result["success"]:
        return jsonify(result), 400
    
    # Generate URLs for the file
    file_id = result["file_id"]
    file_type = result["type"]
    
    # Create response with URLs
    response = {
        "success": True,
        "message": "File uploaded successfully",
        "file_id": file_id,
        "type": file_type,
        "urls": {
            "direct": url_for('media.get_media_file', file_id=file_id, _external=True),
        }
    }
    
    # Add thumbnail URL if it's an image
    if file_type == 'image':
        response["urls"]["thumbnail"] = url_for(
            'media.get_media_file', 
            file_id=file_id, 
            thumbnail='true',
            _external=True
        )
    
    # Add signed URL for secure access
    response["urls"]["signed"] = generate_signed_url(file_id)
    
    return jsonify(response), 201

@bp.route('/<file_id>', methods=['GET'])
def get_media_file(file_id):
    """Get media file from GridFS"""
    use_thumbnail = request.args.get('thumbnail', 'false').lower() == 'true'
    
    # Check for token in query parameter for protected files
    token = request.args.get('token')
    if token:
        decoded_token = validate_token_param(token)
        if not decoded_token:
            return jsonify({"success": False, "message": "Invalid token"}), 401
    
    # For non-image files or when no thumbnail is requested, get the full file
    if not use_thumbnail:
        # Get the file metadata
        media = Media.get_by_id(file_id) or File.get_by_id(file_id)
        
        if not media:
            return jsonify({"success": False, "message": "File not found"}), 404
        
        # Increment view/download count
        if isinstance(media, dict) and "media_type" in media:
            Media.increment_view_count(file_id)
        else:
            File.increment_download_count(file_id)
        
        # Get the actual file from GridFS
        gridfs_id = media.get("filename")
        
        try:
            # Get the file from GridFS
            result = get_file_from_gridfs(gridfs_id)
            
            if not result["success"]:
                return jsonify({"success": False, "message": result["message"]}), 500
            
            # Create file-like object from the data
            file_data = io.BytesIO(result["data"])
            
            # Return the file with appropriate MIME type
            return send_file(
                file_data,
                mimetype=result["mime_type"],
                as_attachment=False,
                download_name=media.get("original_filename")
            )
        except NoFile:
            return jsonify({"success": False, "message": "File content not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "message": f"Error retrieving file: {str(e)}"}), 500
    else:
        # Thumbnail requested, get the media
        media = Media.get_by_id(file_id)
        
        if not media or not media.get("thumbnail"):
            return jsonify({"success": False, "message": "Thumbnail not found"}), 404
        
        # Get the thumbnail from GridFS
        thumbnail_id = media.get("thumbnail")
        
        try:
            # Get the thumbnail from GridFS
            result = get_file_from_gridfs(thumbnail_id)
            
            if not result["success"]:
                return jsonify({"success": False, "message": result["message"]}), 500
            
            # Create file-like object from the data
            file_data = io.BytesIO(result["data"])
            
            # Return the thumbnail with appropriate MIME type
            return send_file(
                file_data,
                mimetype=result["mime_type"],
                as_attachment=False,
                download_name=f"thumb_{media.get('original_filename')}"
            )
        except NoFile:
            return jsonify({"success": False, "message": "Thumbnail content not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "message": f"Error retrieving thumbnail: {str(e)}"}), 500

@bp.route('/<file_id>', methods=['DELETE'])
@jwt_required()
def delete_media_file(file_id):
    """Delete media file"""
    current_user_id = get_jwt_identity()
    
    # Check if the file exists and belongs to the user
    media = Media.get_by_id(file_id)
    file = None
    
    if media:
        # Check if the user has permission to delete
        if str(media.get("uploader_id")) != current_user_id:
            return jsonify({
                "success": False, 
                "message": "You don't have permission to delete this file"
            }), 403
        
        # Delete media
        result = Media.delete(file_id, current_user_id)
        
        if not result:
            return jsonify({"success": False, "message": "Failed to delete media"}), 500
    else:
        # Check if it's a document file
        file = File.get_by_id(file_id)
        
        if not file:
            return jsonify({"success": False, "message": "File not found"}), 404
            
        # Check if the user has permission to delete
        if str(file.get("uploader_id")) != current_user_id:
            return jsonify({
                "success": False, 
                "message": "You don't have permission to delete this file"
            }), 403
        
        # Delete file
        result = File.delete(file_id, current_user_id)
        
        if not result:
            return jsonify({"success": False, "message": "Failed to delete file"}), 500
    
    return jsonify({
        "success": True,
        "message": "File deleted successfully"
    })

# Profile picture routes - these extend the existing user_routes functionality

@bp.route('/users/<user_id>/profile-picture', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def upload_profile_picture(user_id):
    """Upload a new profile picture"""
    current_user_id = get_jwt_identity()
    
    # Ensure users can only update their own profile picture
    if current_user_id != user_id:
        return jsonify({
            "success": False, 
            "message": "Unauthorized to update this profile"
        }), 403
    
    # Check if request has a file
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    
    file = request.files['file']
    
    # Handle the file upload
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
    result = save_profile_picture(file, current_user_id, upload_folder)
    
    if not result["success"]:
        return jsonify(result), 400
    
    # Link the media to the user's profile
    update_result = User.update_profile_picture(current_user_id, result["media_id"])
    
    if update_result["success"]:
        # Add URL to the response for the frontend
        media_id = result["media_id"]
        return jsonify({
            "success": True, 
            "message": "Profile picture updated successfully",
            "media_id": media_id,
            "url": url_for('media.get_user_media', media_id=media_id, _external=True),
            "thumbnail_url": url_for('media.get_user_media', media_id=media_id, thumbnail='true', _external=True)
        }), 200
    else:
        return jsonify(update_result), 500

@bp.route('/users/media/<media_id>', methods=['GET'])
def get_user_media(media_id):
    """Get user media file (public route for profile pictures)"""
    media = Media.get_by_id(media_id)
    
    if not media:
        return jsonify({"success": False, "message": "Media not found"}), 404
    
    # Increment view count
    Media.increment_view_count(media_id)
    
    # Determine if thumbnail or original is requested
    use_thumbnail = request.args.get('thumbnail', 'false').lower() == 'true'
    
    if use_thumbnail and media.get("thumbnail"):
        filename = media["thumbnail"]
    else:
        filename = media["filename"]
    
    # Determine the folder based on media type
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
    
    # Send the file
    return send_file(
        os.path.join(folder, filename),
        mimetype=media.get("mime_type", "image/jpeg"),
        as_attachment=False
    )
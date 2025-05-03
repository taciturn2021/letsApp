import os
import uuid
import magic
import hashlib
import time
import hmac
import mimetypes
from werkzeug.utils import secure_filename
from PIL import Image
from io import BytesIO
from app.models.media import Media
from app.models.file import File
from flask import current_app, url_for
from gridfs import GridFS
from app import mongo
from bson import ObjectId  # Add the missing ObjectId import

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'}

MAX_PROFILE_IMAGE_SIZE = 800 * 1024  # 800KB
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB

THUMBNAIL_SIZE = (150, 150)
PREVIEW_SIZE = (500, 500)

# Initialize GridFS
fs = GridFS(mongo.db)

def allowed_file_type(filename, allowed_extensions):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def allowed_image_file(filename):
    """Check if the file has an allowed image extension"""
    return allowed_file_type(filename, ALLOWED_IMAGE_EXTENSIONS)

def allowed_video_file(filename):
    """Check if the file has an allowed video extension"""
    return allowed_file_type(filename, ALLOWED_VIDEO_EXTENSIONS)

def allowed_audio_file(filename):
    """Check if the file has an allowed audio extension"""
    return allowed_file_type(filename, ALLOWED_AUDIO_EXTENSIONS)

def allowed_document_file(filename):
    """Check if the file has an allowed document extension"""
    return allowed_file_type(filename, ALLOWED_DOCUMENT_EXTENSIONS)

def get_mime_type(file_data):
    """Detect file MIME type"""
    try:
        # Try to use python-magic first
        mime = magic.Magic(mime=True)
        return mime.from_buffer(file_data)
    except Exception as e:
        print(f"[DEBUG] Magic library failed: {str(e)}")
        # Fallback to mimetypes with file signatures
        
        # Get first few bytes to check for common file signatures
        header = file_data[:8] if len(file_data) >= 8 else file_data
        
        # Define some common file signatures
        signatures = {
            b'\xff\xd8\xff': 'image/jpeg',
            b'\x89PNG': 'image/png',
            b'GIF8': 'image/gif',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip',
        }
        
        # Check file signature
        for sig, mime in signatures.items():
            if header.startswith(sig):
                return mime
                
        # If we can't determine from signature, try to guess from extension
        return 'application/octet-stream'

def generate_unique_filename(original_filename):
    """Generate a unique filename for the uploaded file"""
    _, ext = os.path.splitext(original_filename)
    return f"{uuid.uuid4().hex}{ext}"

def generate_signed_url(file_id, expires_in=3600):
    """
    Generate a signed URL for file download with expiration
    
    Parameters:
    - file_id: ID of the file or media
    - expires_in: Expiration time in seconds (default 1 hour)
    """
    # Get secret key from application config
    secret_key = current_app.config['SECRET_KEY']
    
    # Generate expiration timestamp
    expires_at = int(time.time()) + expires_in
    
    # Create signature payload
    payload = f"{file_id}:{expires_at}"
    
    # Generate HMAC signature
    signature = hmac.new(
        key=secret_key.encode(),
        msg=payload.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Construct and return signed URL - use the correct endpoint
    return url_for(
        'media.get_media_file',  # Changed from 'api.download_file' to 'media.get_media_file'
        file_id=file_id,
        expires_at=expires_at,
        signature=signature,
        _external=True
    )

def save_profile_picture(file, uploader_id, upload_folder):
    """
    Save and process a profile picture
    
    Parameters:
    - file: FileStorage object from the request
    - uploader_id: ID of the user uploading the file
    - upload_folder: Path to the upload folder
    
    Returns:
    - Success/failure status and message
    - Media document ID if successful
    """
    print(f"[DEBUG] Starting file upload process...")
    print(f"[DEBUG] Upload folder: {upload_folder}")
    
    # Validate file
    if not file:
        print("[DEBUG] Error: No file provided")
        return {"success": False, "message": "No file provided"}
    
    print(f"[DEBUG] File name: {file.filename}")
    
    if not allowed_image_file(file.filename):
        print(f"[DEBUG] Error: Invalid file type for {file.filename}")
        return {"success": False, "message": "File type not allowed. Allowed types: png, jpg, jpeg, gif, webp"}
    
    # Check file size
    try:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        print(f"[DEBUG] File size: {file_size / 1024:.2f}KB")
        
        if file_size > MAX_PROFILE_IMAGE_SIZE:
            print(f"[DEBUG] Error: File too large ({file_size / 1024:.2f}KB > {MAX_PROFILE_IMAGE_SIZE / 1024}KB)")
            return {"success": False, "message": f"File too large. Maximum size is {MAX_PROFILE_IMAGE_SIZE/1024}KB"}
        
        # Secure the filename and generate a unique name
        original_filename = secure_filename(file.filename)
        filename = generate_unique_filename(original_filename)
        print(f"[DEBUG] Generated unique filename: {filename}")
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(upload_folder, filename)
        print(f"[DEBUG] Saving file to: {file_path}")
        file.save(file_path)
        
        # Generate thumbnail
        try:
            with Image.open(file_path) as img:
                print("[DEBUG] Successfully opened image for thumbnail generation")
                # Get original dimensions
                width, height = img.size
                print(f"[DEBUG] Image dimensions: {width}x{height}")
                
                # Create thumbnail
                thumbnail_filename = f"thumb_{filename}"
                thumbnail_path = os.path.join(upload_folder, thumbnail_filename)
                img.thumbnail(THUMBNAIL_SIZE)
                img.save(thumbnail_path)
                print(f"[DEBUG] Thumbnail saved: {thumbnail_filename}")
                
                # Save media metadata to database
                print("[DEBUG] Saving media metadata to database...")
                media_data = Media.save_media_metadata(
                    filename=filename,
                    original_filename=original_filename,
                    file_size=file_size,
                    media_type=Media.TYPE_IMAGE,
                    mime_type=file.content_type,
                    uploader_id=uploader_id,
                    thumbnail=thumbnail_filename,
                    width=width,
                    height=height
                )
                
                print("[DEBUG] File upload completed successfully")
                return {
                    "success": True,
                    "message": "Profile picture uploaded successfully",
                    "media_id": str(media_data["_id"])
                }
        except Exception as e:
            print(f"[DEBUG] Error processing image: {str(e)}")
            # Clean up files if there was an error
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[DEBUG] Cleaned up file: {file_path}")
            
            thumbnail_path = os.path.join(upload_folder, f"thumb_{filename}")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                print(f"[DEBUG] Cleaned up thumbnail: {thumbnail_path}")
            
            return {"success": False, "message": f"Error processing image: {str(e)}"}
    except Exception as e:
        print(f"[DEBUG] Unexpected error during file upload: {str(e)}")
        return {"success": False, "message": f"Error uploading file: {str(e)}"}

def save_file_to_gridfs(file, uploader_id, file_type=None, message_id=None, group_message_id=None):
    """
    Save a file using GridFS
    
    Parameters:
    - file: FileStorage object from the request
    - uploader_id: ID of the user uploading the file
    - file_type: Optional override for file type detection
    - message_id: Optional ID of the related message (for direct messages)
    - group_message_id: Optional ID of the related group message
    
    Returns:
    - Success/failure status and message
    - File document ID if successful
    """
    # Validate file
    if not file:
        return {"success": False, "message": "No file provided"}
    
    # Secure the filename and generate a unique name
    original_filename = secure_filename(file.filename)
    filename = generate_unique_filename(original_filename)
    
    # Read file data
    file_data = file.read()
    file_size = len(file_data)
    
    # Detect MIME type
    mime_type = get_mime_type(file_data)
    
    # Determine file type if not provided
    if not file_type:
        if mime_type.startswith('image/'):
            if not allowed_image_file(original_filename):
                return {"success": False, "message": "File type not allowed. Allowed image types: png, jpg, jpeg, gif, webp"}
            if file_size > MAX_IMAGE_SIZE:
                return {"success": False, "message": f"File too large. Maximum size is {MAX_IMAGE_SIZE/1024/1024}MB"}
            file_type = 'image'
        elif mime_type.startswith('video/'):
            if not allowed_video_file(original_filename):
                return {"success": False, "message": "File type not allowed. Allowed video types: mp4, webm, mov, avi"}
            if file_size > MAX_VIDEO_SIZE:
                return {"success": False, "message": f"File too large. Maximum size is {MAX_VIDEO_SIZE/1024/1024}MB"}
            file_type = 'video'
        elif mime_type.startswith('audio/'):
            if not allowed_audio_file(original_filename):
                return {"success": False, "message": "File type not allowed. Allowed audio types: mp3, wav, ogg, m4a"}
            if file_size > MAX_AUDIO_SIZE:
                return {"success": False, "message": f"File too large. Maximum size is {MAX_AUDIO_SIZE/1024/1024}MB"}
            file_type = 'audio'
        else:
            if not allowed_document_file(original_filename):
                return {"success": False, "message": "File type not allowed. Allowed document types: pdf, doc, docx, xls, xlsx, ppt, pptx, txt"}
            if file_size > MAX_DOCUMENT_SIZE:
                return {"success": False, "message": f"File too large. Maximum size is {MAX_DOCUMENT_SIZE/1024/1024}MB"}
            file_type = 'document'
    
    try:
        # Create metadata for the file
        metadata = {
            "original_filename": original_filename,
            "file_size": file_size,
            "file_type": file_type,
            "mime_type": mime_type,
            "uploader_id": str(uploader_id)
        }
        
        # Add optional metadata
        if message_id:
            metadata["message_id"] = str(message_id)
        if group_message_id:
            metadata["group_message_id"] = str(group_message_id)
        
        # Store the file in GridFS
        file_id = fs.put(file_data, filename=filename, metadata=metadata)
        
        # Generate preview for images
        thumbnail_id = None
        width = None
        height = None
        
        if file_type == 'image':
            try:
                img = Image.open(BytesIO(file_data))
                width, height = img.size
                
                # Generate thumbnail
                img.thumbnail(PREVIEW_SIZE)
                thumbnail_buffer = BytesIO()
                img.save(thumbnail_buffer, format=img.format)
                thumbnail_data = thumbnail_buffer.getvalue()
                
                # Store thumbnail in GridFS
                thumbnail_metadata = {
                    "original_file_id": str(file_id),
                    "file_type": "thumbnail",
                    "mime_type": mime_type,
                    "uploader_id": str(uploader_id)
                }
                thumbnail_id = fs.put(
                    thumbnail_data,
                    filename=f"thumb_{filename}",
                    metadata=thumbnail_metadata
                )
            except Exception as e:
                print(f"Error generating thumbnail: {str(e)}")
        
        # Save file metadata to the database based on file type
        if file_type in ('image', 'video', 'audio'):
            file_data = Media.save_media_metadata(
                filename=str(file_id),
                original_filename=original_filename,
                file_size=file_size,
                media_type=file_type,
                mime_type=mime_type,
                uploader_id=uploader_id,
                message_id=message_id,
                group_message_id=group_message_id,
                thumbnail=str(thumbnail_id) if thumbnail_id else None,
                width=width,
                height=height
            )
        else:
            file_data = File.save_file_metadata(
                filename=str(file_id),
                original_filename=original_filename,
                file_size=file_size,
                file_type=mime_type,
                uploader_id=uploader_id,
                message_id=message_id,
                group_message_id=group_message_id
            )
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "file_id": str(file_data["_id"]),
            "type": file_type
        }
    except Exception as e:
        return {"success": False, "message": f"Error uploading file: {str(e)}"}

def get_file_from_gridfs(file_id):
    """
    Get a file from GridFS by ID
    
    Parameters:
    - file_id: GridFS ID of the file
    
    Returns:
    - File data, filename, and MIME type
    """
    try:
        # Retrieve the file from GridFS
        grid_out = fs.get(ObjectId(file_id))
        
        # Return file data, filename and MIME type
        return {
            "success": True,
            "data": grid_out.read(),
            "filename": grid_out.filename,
            "mime_type": grid_out.metadata.get("mime_type", "application/octet-stream")
        }
    except Exception as e:
        return {"success": False, "message": f"Error retrieving file: {str(e)}"}
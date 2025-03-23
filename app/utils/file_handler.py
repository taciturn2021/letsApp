import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from app.models.media import Media

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_PROFILE_IMAGE_SIZE = 800 * 1024  # 800KB
THUMBNAIL_SIZE = (150, 150)

def allowed_image_file(filename):
    """Check if the file has an allowed image extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def generate_unique_filename(original_filename):
    """Generate a unique filename for the uploaded file"""
    _, ext = os.path.splitext(original_filename)
    return f"{uuid.uuid4().hex}{ext}"

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
    # Validate file
    if not file:
        return {"success": False, "message": "No file provided"}
    
    if not allowed_image_file(file.filename):
        return {"success": False, "message": "File type not allowed. Allowed types: png, jpg, jpeg, gif"}
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_PROFILE_IMAGE_SIZE:
        return {"success": False, "message": f"File too large. Maximum size is {MAX_PROFILE_IMAGE_SIZE/1024}KB"}
    
    # Secure the filename and generate a unique name
    original_filename = secure_filename(file.filename)
    filename = generate_unique_filename(original_filename)
    
    # Ensure upload folder exists
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save the file
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    # Generate thumbnail
    try:
        with Image.open(file_path) as img:
            # Get original dimensions
            width, height = img.size
            
            # Create thumbnail
            thumbnail_filename = f"thumb_{filename}"
            thumbnail_path = os.path.join(upload_folder, thumbnail_filename)
            img.thumbnail(THUMBNAIL_SIZE)
            img.save(thumbnail_path)
            
            # Save media metadata to database
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
            
            return {
                "success": True,
                "message": "Profile picture uploaded successfully",
                "media_id": str(media_data["_id"])
            }
    except Exception as e:
        # Clean up files if there was an error
        if os.path.exists(file_path):
            os.remove(file_path)
        
        thumbnail_path = os.path.join(upload_folder, f"thumb_{filename}")
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        
        return {"success": False, "message": f"Error processing image: {str(e)}"}
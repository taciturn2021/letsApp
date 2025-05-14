import datetime
from bson import ObjectId
from app import mongo

class Media:
    """Media model for handling image, video, and audio uploads and attachments."""
    
    TYPE_IMAGE = "image"
    TYPE_VIDEO = "video"
    TYPE_AUDIO = "audio"
    
    @staticmethod
    def save_media_metadata(filename, original_filename, file_size, media_type, mime_type, 
                           uploader_id, message_id=None, group_message_id=None,
                           duration=None, thumbnail=None, width=None, height=None):
        """
        Save media metadata to the database
        
        Parameters:
        - filename: The stored filename on the server
        - original_filename: The original name of the uploaded file
        - file_size: Size of the file in bytes
        - media_type: Type of media (image, video, audio)
        - mime_type: MIME type of the file
        - uploader_id: ID of the user who uploaded the media
        - message_id: Optional ID of the related message (for direct messages)
        - group_message_id: Optional ID of the related group message
        - duration: Optional duration in seconds (for audio/video)
        - thumbnail: Optional thumbnail path (for images/videos)
        - width: Optional width in pixels (for images/videos)
        - height: Optional height in pixels (for images/videos)
        """
        media_data = {
            "filename": filename,
            "original_filename": original_filename,
            "file_size": file_size,
            "media_type": media_type,
            "mime_type": mime_type,
            "uploader_id": ObjectId(uploader_id),
            "created_at": datetime.datetime.utcnow(),
            "view_count": 0,
            "is_deleted": False
        }
        
        # Add optional fields if provided
        if duration is not None:
            media_data["duration"] = duration
            
        if thumbnail:
            media_data["thumbnail"] = thumbnail
            
        if width is not None:
            media_data["width"] = width
            
        if height is not None:
            media_data["height"] = height
        
        # Link to message if provided
        if message_id:
            media_data["message_id"] = ObjectId(message_id)
        
        # Link to group message if provided
        if group_message_id:
            media_data["group_message_id"] = ObjectId(group_message_id)
        
        result = mongo.db.media.insert_one(media_data)
        media_data["_id"] = result.inserted_id
        
        return media_data
    
    @staticmethod
    def get_by_id(media_id):
        """Get media metadata by ID"""
        return mongo.db.media.find_one({"_id": ObjectId(media_id), "is_deleted": False})
    
    @staticmethod
    def increment_view_count(media_id):
        """Increment the view count for media"""
        result = mongo.db.media.update_one(
            {"_id": ObjectId(media_id)},
            {"$inc": {"view_count": 1}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def delete(media_id, user_id):
        """
        Soft delete media (only uploader can delete)
        Note: This doesn't delete the physical file, just marks the metadata as deleted
        """
        result = mongo.db.media.update_one(
            {"_id": ObjectId(media_id), "uploader_id": ObjectId(user_id)},
            {"$set": {"is_deleted": True}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def get_user_media(user_id, media_type=None, limit=20, skip=0):
        """
        Get media uploaded by a user with pagination
        
        Parameters:
        - user_id: ID of the user who uploaded the media
        - media_type: Optional filter by media type (image, video, audio)
        - limit: Number of items to return
        - skip: Number of items to skip (for pagination)
        """
        query = {"uploader_id": ObjectId(user_id), "is_deleted": False}
        
        if media_type:
            query["media_type"] = media_type
            
        return list(mongo.db.media.find(query)
                   .sort("created_at", -1)
                   .skip(skip)
                   .limit(limit))
    
    @staticmethod
    def get_most_recent_by_user_and_filename(user_id, filename):
        """
        Find the most recently uploaded media by user that matches or contains the given filename
        
        Parameters:
        - user_id: ID of the uploader
        - filename: Original filename (or part of it) to match
        
        Returns:
        - Most recent matching media document or None
        """
        # First try exact match
        media = mongo.db.media.find_one({
            "uploader_id": ObjectId(user_id),
            "original_filename": filename,
            "is_deleted": False
        }, sort=[("created_at", -1)])
        
        if media:
            return media
            
        # If no exact match, try partial match (case insensitive)
        import re
        pattern = re.compile(f".*{re.escape(filename)}.*", re.IGNORECASE)
        
        return mongo.db.media.find_one({
            "uploader_id": ObjectId(user_id),
            "original_filename": {"$regex": pattern},
            "is_deleted": False
        }, sort=[("created_at", -1)])
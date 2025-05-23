import datetime
from datetime import timezone
import os
import re
from bson import ObjectId
from app import mongo

class File:
    """File model for handling document/non-media file uploads and attachments."""
    
    @staticmethod
    def save_file_metadata(filename, original_filename, file_size, file_type, uploader_id, 
                          message_id=None, group_message_id=None):
        """
        Save file metadata to the database for document files
        
        Parameters:
        - filename: The stored filename on the server
        - original_filename: The original name of the uploaded file
        - file_size: Size of the file in bytes
        - file_type: MIME type of the file
        - uploader_id: ID of the user who uploaded the file
        - message_id: Optional ID of the related message (for direct messages)
        - group_message_id: Optional ID of the related group message
        """
        file_data = {
            "filename": filename,
            "original_filename": original_filename,
            "file_size": file_size,
            "file_type": file_type,
            "uploader_id": ObjectId(uploader_id),
            "created_at": datetime.datetime.now(timezone.utc),
            "download_count": 0,
            "is_deleted": False
        }
        
        # Link to message if provided
        if message_id:
            file_data["message_id"] = ObjectId(message_id)
        
        # Link to group message if provided
        if group_message_id:
            file_data["group_message_id"] = ObjectId(group_message_id)
        
        result = mongo.db.files.insert_one(file_data)
        file_data["_id"] = result.inserted_id
        
        return file_data
    
    @staticmethod
    def get_by_id(file_id):
        """Get file metadata by ID"""
        return mongo.db.files.find_one({"_id": ObjectId(file_id), "is_deleted": False})
    
    @staticmethod
    def increment_download_count(file_id):
        """Increment the download count for a file"""
        result = mongo.db.files.update_one(
            {"_id": ObjectId(file_id)},
            {"$inc": {"download_count": 1}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def delete(file_id, user_id):
        """
        Soft delete a file (only uploader can delete)
        Note: This doesn't delete the physical file, just marks the metadata as deleted
        """
        result = mongo.db.files.update_one(
            {"_id": ObjectId(file_id), "uploader_id": ObjectId(user_id)},
            {"$set": {"is_deleted": True}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def get_user_files(user_id, limit=20, skip=0):
        """Get files uploaded by a user with pagination"""
        return list(mongo.db.files.find(
            {"uploader_id": ObjectId(user_id), "is_deleted": False}
        ).sort("created_at", -1).skip(skip).limit(limit))
    
    @staticmethod
    def get_most_recent_by_user_and_filename(user_id, filename):
        """
        Find the most recently uploaded file by user that matches or contains the given filename
        
        Parameters:
        - user_id: ID of the uploader
        - filename: Original filename (or part of it) to match
        
        Returns:
        - Most recent matching file document or None
        """
        try:
            # First try exact match
            file = mongo.db.files.find_one({
                "uploader_id": ObjectId(user_id),
                "original_filename": filename,
                "is_deleted": False
            }, sort=[("created_at", -1)])
            
            if file:
                return file
                
            # If no exact match, try partial match (case insensitive)
            pattern = re.compile(f".*{re.escape(filename)}.*", re.IGNORECASE)
            
            return mongo.db.files.find_one({
                "uploader_id": ObjectId(user_id),
                "original_filename": {"$regex": pattern},
                "is_deleted": False
            }, sort=[("created_at", -1)])
        except Exception as e:
            print(f"Error finding file by filename: {str(e)}")
            return None

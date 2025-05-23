import datetime
from datetime import timezone
from bson import ObjectId
from app import mongo
import gridfs

class Group:
    """Group model for group chats."""
    
    @staticmethod
    def create(name, creator_id, description=None, icon=None):
        """
        Create a new group
        
        Parameters:
        - name: Name of the group
        - creator_id: ID of the user creating the group
        - description: Optional group description
        - icon: Optional group icon/image
        """
        group = {
            "name": name,
            "description": description,
            "icon": icon,
            "creator_id": ObjectId(creator_id),
            "members": [ObjectId(creator_id)],  # Creator is the first member
            "admins": [ObjectId(creator_id)],   # Creator is the first admin
            "created_at": datetime.datetime.now(timezone.utc),
            "updated_at": datetime.datetime.now(timezone.utc),
            "is_active": True,
            "version": 1  # Add version field for optimistic locking
        }
        
        result = mongo.db.groups.insert_one(group)
        group["_id"] = result.inserted_id
        return group
    
    @staticmethod
    def get_by_id(group_id):
        """Get group by ID"""
        return mongo.db.groups.find_one({"_id": ObjectId(group_id), "is_active": True})
    
    @staticmethod
    def get_user_groups(user_id):
        """Get all groups a user is a member of"""
        return list(mongo.db.groups.find(
            {"members": ObjectId(user_id), "is_active": True}
        ).sort("updated_at", -1))
    
    @staticmethod
    def add_member(group_id, user_id, admin_id, max_retries=3):
        """Add a member to the group (admin only) with optimistic locking"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            admin_obj_id = ObjectId(admin_id)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                
                # Check permissions
                if admin_obj_id not in group.get('admins', []):
                    return {"success": False, "message": "Only admins can add members"}
                
                # Check if user is already a member
                if user_obj_id in group.get('members', []):
                    return {"success": False, "message": "User is already a member"}
                
                current_version = group.get('version', 1)
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$push": {"members": user_obj_id},
                        "$set": {"updated_at": datetime.datetime.now(timezone.utc)},
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "Member added successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to add member due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to add member after retries"}
            
        except Exception as e:
            print(f"Error adding member to group: {e}")
            return {"success": False, "message": f"Error adding member: {str(e)}"}
    
    @staticmethod
    def remove_member(group_id, user_id, admin_id, max_retries=3):
        """Remove a member from the group (admin only or self-removal) with optimistic locking"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            admin_obj_id = ObjectId(admin_id)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                
                # Check permissions (admin or self-removal)
                is_admin = admin_obj_id in group.get('admins', [])
                is_self_removal = str(user_id) == str(admin_id)
                
                if not is_admin and not is_self_removal:
                    return {"success": False, "message": "Permission denied"}
                
                # Check if user is a member
                if user_obj_id not in group.get('members', []):
                    return {"success": False, "message": "User is not a member"}
                
                current_version = group.get('version', 1)
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$pull": {
                            "members": user_obj_id,
                            "admins": user_obj_id
                        },
                        "$set": {"updated_at": datetime.datetime.now(timezone.utc)},
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "Member removed successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to remove member due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to remove member after retries"}
            
        except Exception as e:
            print(f"Error removing member from group: {e}")
            return {"success": False, "message": f"Error removing member: {str(e)}"}
    
    @staticmethod
    def make_admin(group_id, user_id, action_by, max_retries=3):
        """Make a user an admin of a group with optimistic locking"""
        try:
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            action_by_obj_id = ObjectId(action_by)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                
                # Verify permissions
                if action_by_obj_id not in group.get("admins", []):
                    return {"success": False, "message": "Only admins can promote members"}
                
                if user_obj_id not in group.get("members", []):
                    return {"success": False, "message": "User is not a member"}
                
                if user_obj_id in group.get("admins", []):
                    return {"success": False, "message": "User is already an admin"}
                
                current_version = group.get('version', 1)
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$addToSet": {"admins": user_obj_id},
                        "$set": {"updated_at": datetime.datetime.now(timezone.utc)},
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "User promoted to admin successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to promote user due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to promote user after retries"}
            
        except Exception as e:
            print(f"Error making user admin: {e}")
            return {"success": False, "message": f"Error promoting user: {str(e)}"}
    
    @staticmethod
    def update(group_id, update_data, admin_id, max_retries=3):
        """Update group information (admin only) with optimistic locking"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            admin_obj_id = ObjectId(admin_id)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                
                if admin_obj_id not in group.get('admins', []):
                    return {"success": False, "message": "Only admins can update group information"}
                
                current_version = group.get('version', 1)
                
                # Prepare update data
                update_fields = {**update_data, "updated_at": datetime.datetime.now(timezone.utc)}
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$set": update_fields,
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "Group updated successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to update group due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to update group after retries"}
            
        except Exception as e:
            print(f"Error updating group: {e}")
            return {"success": False, "message": f"Error updating group: {str(e)}"}
    
    @staticmethod
    def update_icon(group_id, media_id, user_id, max_retries=3):
        """Update group icon (only admins) with optimistic locking"""
        try:
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                
                # Verify permissions - only admins can update icon
                if user_obj_id not in group.get("admins", []):
                    return {"success": False, "message": "Only admins can update group icon"}
                
                current_version = group.get('version', 1)
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$set": {
                            "icon": media_id,
                            "updated_at": datetime.datetime.now(timezone.utc)
                        },
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "Group icon updated successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to update icon due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to update icon after retries"}
            
        except Exception as e:
            print(f"Error updating group icon: {e}")
            return {"success": False, "message": f"Error updating icon: {str(e)}"}
    
    @staticmethod
    def remove_icon(group_id, admin_id, max_retries=3):
        """Remove group icon (admin only) with optimistic locking"""
        try:
            group_obj_id = ObjectId(group_id)
            admin_obj_id = ObjectId(admin_id)
            
            for attempt in range(max_retries):
                # Get current group with version
                group = mongo.db.groups.find_one({"_id": group_obj_id})
                if not group:
                    return {"success": False, "message": "Group not found"}
                    
                # Check if user is admin
                if admin_obj_id not in group.get('admins', []):
                    return {"success": False, "message": "Only admins can remove group icon"}
                
                current_version = group.get('version', 1)
                
                # Remove icon from GridFS if exists
                if group.get('icon'):
                    fs = gridfs.GridFS(mongo.db)
                    try:
                        fs.delete(ObjectId(group['icon']))
                    except Exception as e:
                        print(f"Error deleting icon file: {e}")
                
                # Attempt optimistic update
                result = mongo.db.groups.update_one(
                    {
                        "_id": group_obj_id,
                        "version": current_version  # Optimistic lock check
                    },
                    {
                        "$unset": {"icon": ""},
                        "$set": {"updated_at": datetime.datetime.now(timezone.utc)},
                        "$inc": {"version": 1}  # Increment version
                    }
                )
                
                if result.modified_count > 0:
                    return {"success": True, "message": "Group icon removed successfully"}
                
                # If we reach here, there was a concurrent modification
                if attempt == max_retries - 1:
                    return {"success": False, "message": "Failed to remove icon due to concurrent modifications"}
                
                # Small delay before retry
                import time
                time.sleep(0.1)
            
            return {"success": False, "message": "Failed to remove icon after retries"}
            
        except Exception as e:
            print(f"Error removing group icon: {e}")
            return {"success": False, "message": f"Error removing icon: {str(e)}"}

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
            "is_active": True
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
    def add_member(group_id, user_id, admin_id):
        """Add a member to the group (admin only)"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            admin_obj_id = ObjectId(admin_id)
            
            # Check if group exists and admin has permission
            group = mongo.db.groups.find_one({"_id": group_obj_id})
            if not group:
                return False
            
            if admin_obj_id not in group.get('admins', []):
                return False
            
            # Check if user is already a member
            if user_obj_id in group.get('members', []):
                return False
            
            # Add user to members list
            result = mongo.db.groups.update_one(
                {"_id": group_obj_id},
                {
                    "$push": {"members": user_obj_id},
                    "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error adding member to group: {e}")
            return False
    
    @staticmethod
    def remove_member(group_id, user_id, admin_id):
        """Remove a member from the group (admin only or self-removal)"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            user_obj_id = ObjectId(user_id)
            admin_obj_id = ObjectId(admin_id)
            
            # Check if group exists
            group = mongo.db.groups.find_one({"_id": group_obj_id})
            if not group:
                return False
            
            # Check permissions (admin or self-removal)
            is_admin = admin_obj_id in group.get('admins', [])
            is_self_removal = str(user_id) == str(admin_id)
            
            if not is_admin and not is_self_removal:
                return False
            
            # Check if user is a member
            if user_obj_id not in group.get('members', []):
                return False
            
            # Remove user from members and admins lists
            result = mongo.db.groups.update_one(
                {"_id": group_obj_id},
                {
                    "$pull": {
                        "members": user_obj_id,
                        "admins": user_obj_id
                    },
                    "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error removing member from group: {e}")
            return False
    
    @staticmethod
    def make_admin(group_id, user_id, action_by):
        """Make a user an admin of a group"""
        group = Group.get_by_id(group_id)
        
        # Verify permissions
        if not group or ObjectId(action_by) not in group["admins"] or ObjectId(user_id) not in group["members"]:
            return False
        
        # Make user an admin
        result = mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$addToSet": {"admins": ObjectId(user_id)},
                "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def update(group_id, update_data, admin_id):
        """Update group information (admin only)"""
        try:
            # Convert IDs to ObjectId
            group_obj_id = ObjectId(group_id)
            admin_obj_id = ObjectId(admin_id)
            
            # Check if group exists and admin has permission
            group = mongo.db.groups.find_one({"_id": group_obj_id})
            if not group:
                return False
            
            if admin_obj_id not in group.get('admins', []):
                return False
            
            # Prepare update data
            update_fields = {**update_data, "updated_at": datetime.datetime.now(timezone.utc)}
            
            result = mongo.db.groups.update_one(
                {"_id": group_obj_id},
                {"$set": update_fields}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error updating group: {e}")
            return False
    
    @staticmethod
    def update_icon(group_id, media_id, user_id):
        """Update group icon (only admins)"""
        group = Group.get_by_id(group_id)
        
        # Verify permissions - only admins can update icon
        if not group or ObjectId(user_id) not in group["admins"]:
            return False
        
        result = mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$set": {
                    "icon": media_id,
                    "updated_at": datetime.datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def remove_icon(group_id, admin_id):
        """Remove group icon (admin only)"""
        try:
            # Get the group first
            group = Group.get_by_id(group_id)
            if not group:
                return False
                
            # Check if user is admin
            if ObjectId(admin_id) not in group.get('admins', []):
                return False
            
            # Remove icon from GridFS if exists
            if group.get('icon'):
                fs = gridfs.GridFS(mongo.db)
                try:
                    fs.delete(ObjectId(group['icon']))
                except Exception as e:
                    print(f"Error deleting icon file: {e}")
            
            # Update group document
            result = mongo.db.groups.update_one(
                {"_id": ObjectId(group_id)},
                {
                    "$unset": {"icon": ""},
                    "$set": {"updated_at": datetime.datetime.now(timezone.utc)}
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error removing group icon: {e}")
            return False

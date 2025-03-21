import datetime
from bson import ObjectId
from app import mongo

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
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
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
    def add_member(group_id, user_id, added_by):
        """Add a user to a group"""
        # Check if user is already a member
        group = Group.get_by_id(group_id)
        if not group or ObjectId(user_id) in group["members"]:
            return False
        
        # Add user to the group
        result = mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$push": {"members": ObjectId(user_id)},
                "$set": {"updated_at": datetime.datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def remove_member(group_id, user_id, removed_by):
        """Remove a user from a group"""
        group = Group.get_by_id(group_id)
        
        # Check if group exists and user is a member
        if not group or ObjectId(user_id) not in group["members"]:
            return False
        
        # Check if removed_by is an admin
        if ObjectId(removed_by) not in group["admins"]:
            # Allow self-removal
            if user_id != removed_by:
                return False
        
        # Remove user from members and admins
        result = mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$pull": {
                    "members": ObjectId(user_id),
                    "admins": ObjectId(user_id)
                },
                "$set": {"updated_at": datetime.datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
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
                "$set": {"updated_at": datetime.datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def update(group_id, update_data, user_id):
        """Update group information (only admins)"""
        group = Group.get_by_id(group_id)
        
        # Verify permissions
        if not group or ObjectId(user_id) not in group["admins"]:
            return False
        
        # Filter allowed fields
        allowed_fields = ["name", "description", "icon"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if update_dict:
            update_dict["updated_at"] = datetime.datetime.utcnow()
            
            result = mongo.db.groups.update_one(
                {"_id": ObjectId(group_id)},
                {"$set": update_dict}
            )
            
            return result.modified_count > 0
        
        return False

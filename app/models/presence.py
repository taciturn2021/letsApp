import datetime
from bson import ObjectId
from app import mongo

class Presence:
    """Presence model for tracking user online/offline status."""
    
    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    
    @staticmethod
    def update_status(user_id, status):
        """
        Update a user's online status
        
        Parameters:
        - user_id: ID of the user
        - status: Status (online, offline)
        """
        now = datetime.datetime.utcnow()
        
        # Find existing presence record
        presence = mongo.db.presence.find_one({"user_id": ObjectId(user_id)})
        
        if presence:
            # Update existing record
            result = mongo.db.presence.update_one(
                {"user_id": ObjectId(user_id)},
                {
                    "$set": {
                        "status": status,
                        "last_updated": now
                    }
                }
            )
        else:
            # Create new record
            result = mongo.db.presence.insert_one({
                "user_id": ObjectId(user_id),
                "status": status,
                "last_updated": now,
                "last_active": now
            })
        
        # Also update the user's last_seen timestamp
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_seen": now}}
        )
        
        return True
    
    @staticmethod
    def get_status(user_id):
        """Get a user's current status"""
        presence = mongo.db.presence.find_one({"user_id": ObjectId(user_id)})
        
        if not presence:
            return Presence.STATUS_OFFLINE
            
        # Check if online status is stale (more than 10 minutes old)
        if presence["status"] == Presence.STATUS_ONLINE:
            time_diff = datetime.datetime.utcnow() - presence["last_updated"]
            if time_diff.total_seconds() > 600:  # 10 minutes instead of 2
                # Return offline status but don't update the database
                # This way, a reconnecting socket can still claim the status
                return Presence.STATUS_OFFLINE
        
        return presence["status"]
    
    @staticmethod
    def get_contacts_status(user_id):
        """Get status of all contacts for a user"""
        # Get all accepted contacts
        contacts = mongo.db.contacts.find({
            "user_id": ObjectId(user_id),
            "status": "accepted"
        })
        
        contact_ids = [contact["contact_id"] for contact in contacts]
        
        if not contact_ids:
            return []
        
        # Get presence information for all contacts
        presence_list = list(mongo.db.presence.find({
            "user_id": {"$in": contact_ids}
        }))
        
        # Create a lookup dictionary
        presence_by_id = {str(p["user_id"]): p for p in presence_list}
        
        # Get basic user info for all contacts
        users = list(mongo.db.users.find(
            {"_id": {"$in": contact_ids}},
            {"username": 1, "profile_picture": 1}
        ))
        
        # Combine the data
        result = []
        for user in users:
            user_id_str = str(user["_id"])
            presence_data = presence_by_id.get(user_id_str, {})
            
            # Check if online status is stale
            status = presence_data.get("status", Presence.STATUS_OFFLINE)
            if status == Presence.STATUS_ONLINE:
                if "last_updated" in presence_data:
                    time_diff = datetime.datetime.utcnow() - presence_data["last_updated"]
                    if time_diff.total_seconds() > 600:  # 10 minutes instead of 2
                        status = Presence.STATUS_OFFLINE
            
            # Convert datetime objects to ISO format strings
            last_active = presence_data.get("last_active")
            if last_active:
                last_active = last_active.isoformat()
            
            result.append({
                "user_id": user["_id"],
                "username": user["username"],
                "profile_picture": user.get("profile_picture"),
                "status": status,
                "last_active": last_active
            })
            
        return result
    
    @staticmethod
    def update_last_active(user_id):
        """Update the last active timestamp for a user"""
        now = datetime.datetime.utcnow()
        
        result = mongo.db.presence.update_one(
            {"user_id": ObjectId(user_id)},
            {
                "$set": {
                    "last_active": now,
                    "last_updated": now
                }
            },
            upsert=True
        )
        
        return True

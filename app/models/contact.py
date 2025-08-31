import datetime
from bson import ObjectId
from app import mongo

class Contact:
    """Contact model for managing user connections."""
    
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_BLOCKED = "blocked"
    
    @staticmethod
    def add_contact(user_id, contact_id):
        """
        Add a user as contact (creates a pending connection)
        
        Parameters:
        - user_id: ID of the user adding the contact
        - contact_id: ID of the user being added as contact
        """
        # Check if contact already exists
        existing = mongo.db.contacts.find_one({
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id)
        })
        
        if existing:
            return None
            
        contact = {
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id),
            "status": Contact.STATUS_PENDING,
            "created_at": datetime.datetime.now(timezone.utc),
            "updated_at": datetime.datetime.now(timezone.utc),
            "notes": "",
            "is_favorite": False
        }
        
        result = mongo.db.contacts.insert_one(contact)
        contact["_id"] = result.inserted_id
        return contact
    
    @staticmethod
    def accept_contact(user_id, contact_id):
        """Accept a contact request"""
        # First check if the request exists
        request = mongo.db.contacts.find_one({
            "user_id": ObjectId(contact_id),
            "contact_id": ObjectId(user_id),
            "status": Contact.STATUS_PENDING
        })
        
        if not request:
            return False
        
        # Update the request status
        mongo.db.contacts.update_one(
            {"_id": request["_id"]},
            {
                "$set": {
                    "status": Contact.STATUS_ACCEPTED,
                    "updated_at": datetime.datetime.now(timezone.utc)
                }
            }
        )
        
        # Create a reciprocal contact entry
        existing = mongo.db.contacts.find_one({
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id)
        })
        
        if not existing:
            mongo.db.contacts.insert_one({
                "user_id": ObjectId(user_id),
                "contact_id": ObjectId(contact_id),
                "status": Contact.STATUS_ACCEPTED,
                "created_at": datetime.datetime.now(timezone.utc),
                "updated_at": datetime.datetime.now(timezone.utc),
                "notes": "",
                "is_favorite": False
            })
        else:
            mongo.db.contacts.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "status": Contact.STATUS_ACCEPTED,
                        "updated_at": datetime.datetime.now(timezone.utc)
                    }
                }
            )
        
        return True
    
    @staticmethod
    def block_contact(user_id, contact_id):
        """Block a contact"""
        # Check if contact exists
        contact = mongo.db.contacts.find_one({
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id)
        })
        
        if contact:
            # Update existing contact
            result = mongo.db.contacts.update_one(
                {"_id": contact["_id"]},
                {
                    "$set": {
                        "status": Contact.STATUS_BLOCKED,
                        "updated_at": datetime.datetime.now(timezone.utc)
                    }
                }
            )
        else:
            # Create new blocked contact
            result = mongo.db.contacts.insert_one({
                "user_id": ObjectId(user_id),
                "contact_id": ObjectId(contact_id),
                "status": Contact.STATUS_BLOCKED,
                "created_at": datetime.datetime.now(timezone.utc),
                "updated_at": datetime.datetime.now(timezone.utc),
                "notes": "",
                "is_favorite": False
            })
            
        return True
    
    @staticmethod
    def unblock_contact(user_id, contact_id):
        """Unblock a contact"""
        result = mongo.db.contacts.update_one(
            {
                "user_id": ObjectId(user_id),
                "contact_id": ObjectId(contact_id),
                "status": Contact.STATUS_BLOCKED
            },
            {
                "$set": {
                    "status": Contact.STATUS_ACCEPTED,
                    "updated_at": datetime.datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    def remove_contact(user_id, contact_id):
        """Remove a contact"""
        result = mongo.db.contacts.delete_one({
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id)
        })
        return result.deleted_count > 0
    
    @staticmethod
    def get_contacts(user_id, status=None, limit=50, skip=0):
        """Get all contacts for a user with optional filtering by status"""
        query = {"user_id": ObjectId(user_id)}
        
        if status:
            query["status"] = status
            
        contacts = list(mongo.db.contacts.find(query)
                       .sort([("is_favorite", -1), ("updated_at", -1)])
                       .skip(skip).limit(limit))
        
        return contacts
    
    @staticmethod
    def is_contact(user_id, contact_id, status=None):
        """Check if a user is a contact"""
        query = {
            "user_id": ObjectId(user_id),
            "contact_id": ObjectId(contact_id)
        }
        
        if status:
            query["status"] = status
            
        contact = mongo.db.contacts.find_one(query)
        return contact is not None
    
    @staticmethod
    def set_favorite(user_id, contact_id, is_favorite):
        """Mark/unmark a contact as favorite"""
        result = mongo.db.contacts.update_one(
            {
                "user_id": ObjectId(user_id),
                "contact_id": ObjectId(contact_id)
            },
            {
                "$set": {
                    "is_favorite": is_favorite,
                    "updated_at": datetime.datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count > 0
